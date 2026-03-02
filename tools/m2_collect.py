#!/usr/bin/env python3
"""Collect Macaulay2 Core introspection data into JSONL records."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


M2_CMD = ["M2", "--silent", "--no-prompts", "-q", "-e"]


@dataclass(frozen=True)
class Probe:
    name: str
    expression_template: str


PROBES: tuple[Probe, ...] = (
    Probe("symbol_class", 'class(getGlobalSymbol "{symbol}")'),
    Probe("runtime_class", 'class(value getGlobalSymbol "{symbol}")'),
    Probe("parent", 'parent(value getGlobalSymbol "{symbol}")'),
    Probe("methods", 'methods(value getGlobalSymbol "{symbol}")'),
    Probe("options", 'options(value getGlobalSymbol "{symbol}")'),
    Probe("peek", 'peek(value getGlobalSymbol "{symbol}")'),
    Probe("show_structure", 'toString net showStructure(value getGlobalSymbol "{symbol}")'),
    Probe("to_string", 'toString(value getGlobalSymbol "{symbol}")'),
    Probe("help_text", '(load "tools/help_probe.m2"; helpProbeText("{symbol}", {include_methods}))'),
    Probe("operator_attributes", 'operatorAttributes(getGlobalSymbol "{symbol}")'),
)

PROBES_BY_NAME: dict[str, Probe] = {probe.name: probe for probe in PROBES}
ROW_PREFIX = "M2ROW|"
ERROR_MARKER = "__M2_PROBE_ERROR__"


def _escape_m2_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def run_m2(expression: str) -> tuple[int, str, str, float]:
    started = time.time()
    process = subprocess.run(
        [*M2_CMD, f"print toExternalString({expression})"],
        capture_output=True,
        text=True,
    )
    duration_ms = (time.time() - started) * 1000.0
    return process.returncode, process.stdout.strip(), process.stderr.strip(), duration_ms


def _probe_line(name: str, expression: str) -> str:
    escaped_marker = _escape_m2_string(ERROR_MARKER)
    escaped_name = _escape_m2_string(name)
    return (
        f'v := try toExternalString({expression}) else "{escaped_marker}"; '
        f'print("{ROW_PREFIX}{escaped_name}|" | v);'
    )


def run_m2_batch(symbol: str, selected_probes: list[Probe], args: argparse.Namespace) -> tuple[int, str, str, float]:
    escaped_symbol = _escape_m2_string(symbol)
    script_parts = [
        f's := getGlobalSymbol "{escaped_symbol}";',
        "x := value s;",
    ]
    for probe in selected_probes:
        expression = expression_for_probe(probe, escaped_symbol, args)
        # Reuse already-bound values to avoid repeated global lookups.
        expression = expression.replace(f'getGlobalSymbol "{escaped_symbol}"', "s")
        expression = expression.replace("value s", "x")
        script_parts.append(_probe_line(probe.name, expression))
    batch_expression = " ".join(script_parts)
    return run_m2(f"( {batch_expression} )")


def parse_batch_rows(stdout: str, selected_probes: list[Probe]) -> dict[str, tuple[bool, str, str]]:
    rows: dict[str, tuple[bool, str, str]] = {}
    expected = {probe.name for probe in selected_probes}
    for line in stdout.splitlines():
        if not line.startswith(ROW_PREFIX):
            continue
        payload = line[len(ROW_PREFIX) :]
        if "|" not in payload:
            continue
        name, value = payload.split("|", 1)
        if name not in expected:
            continue
        if value == ERROR_MARKER:
            rows[name] = (False, "", "probe evaluation failed")
        else:
            rows[name] = (True, value, "")
    return rows


def expression_for_probe(probe: Probe, escaped_symbol: str, args: argparse.Namespace) -> str:
    include_methods = "true" if args.help_method_docs else "false"
    return probe.expression_template.format(symbol=escaped_symbol, include_methods=include_methods)


def collect_symbol(
    symbol: str,
    selected_probes: list[Probe],
    run_id: str,
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    code, stdout, stderr, duration_ms = run_m2_batch(symbol, selected_probes, args)
    parsed = parse_batch_rows(stdout, selected_probes)
    rows: list[dict[str, object]] = []
    per_probe_duration = (duration_ms / len(selected_probes)) if selected_probes else 0.0

    for probe in selected_probes:
        escaped_symbol = _escape_m2_string(symbol)
        expression = expression_for_probe(probe, escaped_symbol, args)
        probe_ok, probe_stdout, probe_stderr = parsed.get(probe.name, (False, "", "probe output missing"))
        if code != 0 and stderr:
            probe_ok = False
            probe_stdout = ""
            probe_stderr = stderr
        rows.append(
            {
                "runId": run_id,
                "symbol": symbol,
                "probe": probe.name,
                "expression": expression,
                "ok": probe_ok,
                "exitCode": code,
                "stdout": probe_stdout,
                "stderr": probe_stderr,
                "durationMs": round(per_probe_duration, 3),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
    return rows


def list_core_symbols() -> list[str]:
    command = 'scan(Core#"exported symbols", s -> print toString s)'
    process = subprocess.run([*M2_CMD, command], capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or "failed to list symbols")
    symbols = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    return sorted(set(symbols), key=str.casefold)


def iter_symbols(args: argparse.Namespace) -> Iterable[str]:
    if args.symbol:
        return sorted(set(args.symbol), key=str.casefold)
    return list_core_symbols()


def collect(args: argparse.Namespace) -> int:
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    symbols = list(iter_symbols(args))
    selected_probes = list(iter_probes(args))
    run_id = time.strftime("%Y%m%d-%H%M%S")

    started = time.time()
    total = len(symbols)

    def should_print_progress(completed: int) -> bool:
        if completed == 1 or completed == total:
            return True
        return completed % args.progress_every == 0

    def format_duration(seconds: float) -> str:
        if seconds < 0:
            seconds = 0
        whole = int(seconds)
        hours, remainder = divmod(whole, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def print_progress(completed: int, symbol: str) -> None:
        elapsed = time.time() - started
        rate = completed / elapsed if elapsed > 0 else 0.0
        remaining = total - completed
        eta_seconds = remaining / rate if rate > 0 else -1.0
        percent = (completed / total * 100.0) if total else 100.0
        print(
            f"[{completed}/{total}] {percent:5.1f}% symbol={symbol} "
            f"elapsed={format_duration(elapsed)} eta={format_duration(eta_seconds)}",
            flush=True,
        )

    with output_path.open("w", encoding="utf-8") as handle:
        if args.jobs <= 1:
            for completed, symbol in enumerate(symbols, start=1):
                rows = collect_symbol(symbol, selected_probes, run_id, args)
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                if should_print_progress(completed):
                    print_progress(completed, symbol)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
                futures = {
                    executor.submit(collect_symbol, symbol, selected_probes, run_id, args): symbol
                    for symbol in symbols
                }
                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    symbol = futures[future]
                    rows = future.result()
                    for row in rows:
                        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    completed += 1
                    if should_print_progress(completed):
                        print_progress(completed, symbol)

    print(
        f"Collected {len(symbols)} symbols with {len(selected_probes)} probes into {output_path} "
        f"(jobs={args.jobs}, help_method_docs={args.help_method_docs})"
    )
    return 0


def iter_probes(args: argparse.Namespace) -> Iterable[Probe]:
    if not args.probe:
        return PROBES
    names = sorted(set(args.probe), key=str.casefold)
    missing = [name for name in names if name not in PROBES_BY_NAME]
    if missing:
        available = ", ".join(sorted(PROBES_BY_NAME))
        raise ValueError(f"unknown probe(s): {', '.join(missing)}; available: {available}")
    return [PROBES_BY_NAME[name] for name in names]


def build_parser() -> argparse.ArgumentParser:
    default_jobs = min(8, max(1, os.cpu_count() or 1))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="data/core/raw/latest.jsonl",
        help="JSONL output path",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        help="Collect only this symbol (repeatable). If omitted, collect all Core exported symbols.",
    )
    parser.add_argument(
        "--probe",
        action="append",
        help="Collect only this probe (repeatable). If omitted, collect all probes.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=default_jobs,
        help=f"Worker threads for symbol-level parallelism (default: {default_jobs}).",
    )
    parser.add_argument(
        "--help-method-docs",
        action="store_true",
        help="Include per-method help parsing in help_text probe (slower).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=50,
        help="Print progress every N symbols (default: 50).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.jobs < 1:
            raise ValueError("--jobs must be >= 1")
        if args.progress_every < 1:
            raise ValueError("--progress-every must be >= 1")
        return collect(args)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
