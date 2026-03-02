#!/usr/bin/env python3
"""Normalize raw Macaulay2 probe JSONL into graph-oriented JSON artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


METHOD_TUPLE_RE = re.compile(r"\(([^)]*)\)")
OPTION_KEY_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_']*)\s*=>")
OUTPUT_TYPE_RE = re.compile(r"^o\d+\s*:\s*(.+)$")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def canonical_id(kind: str, name: str) -> str:
    safe_name = re.sub(r"\s+", "_", name.strip())
    return f"core::{kind}::{safe_name}"


def classify_kind(symbol: str, runtime_class: str | None, symbol_class: str | None) -> str:
    if runtime_class and runtime_class.startswith("MethodFunction"):
        if symbol_class == "Keyword":
            return "operator"
        return "function"
    if runtime_class in {"Type", "ImmutableType"}:
        return "type"
    return "symbol"


def parse_methods(raw: str) -> list[dict[str, Any]]:
    methods: list[dict[str, Any]] = []
    for match in METHOD_TUPLE_RE.finditer(raw):
        entries = [part.strip() for part in match.group(1).split(",")]
        if len(entries) < 2:
            continue
        name = entries[0]
        inputs = entries[1:]
        signature = f"{name}({', '.join(inputs)})"
        signature_id = f"{name}({','.join(inputs)})"
        methods.append(
            {
                "name": name,
                "inputs": inputs,
                "signature": signature,
                "signature_id": signature_id,
            }
        )
    return methods


def parse_signature_id(signature_id: str) -> dict[str, Any] | None:
    opening = signature_id.find("(")
    closing = signature_id.rfind(")")
    if opening <= 0 or closing <= opening:
        return None
    name = signature_id[:opening].strip()
    raw_inputs = signature_id[opening + 1 : closing].strip()
    inputs = [item.strip() for item in raw_inputs.split(",")] if raw_inputs else []
    signature = f"{name}({', '.join(inputs)})"
    return {
        "name": name,
        "inputs": inputs,
        "signature": signature,
        "signature_id": signature_id,
    }


def parse_options(raw: str) -> list[str]:
    if raw == "null" or not raw:
        return []
    symbols = OPTION_KEY_RE.findall(raw)
    return sorted(set(symbols), key=str.casefold)


def decode_external_string(raw: str) -> str:
    text = raw.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        try:
            decoded = json.loads(text)
            if isinstance(decoded, str):
                return decoded
        except json.JSONDecodeError:
            return raw
    return raw


def _unquote_way_item(value: str) -> str:
    item = value.strip()
    if not item.startswith('"'):
        return item
    closing = item.find('"', 1)
    if closing <= 0:
        return item
    signature = item[1:closing]
    remainder = item[closing + 1 :].strip()
    return signature if not remainder else f"{signature} {remainder}"


def _extract_output_descriptions(examples: list[str]) -> list[str]:
    outputs: list[str] = []
    seen: set[str] = set()
    for example in examples:
        for raw_line in example.splitlines():
            line = raw_line.strip()
            if not line.startswith("|"):
                continue
            body = line.strip("|").strip()
            match = OUTPUT_TYPE_RE.match(body)
            if not match:
                continue
            value = match.group(1).strip()
            if value and value not in seen:
                seen.add(value)
                outputs.append(value)
    return outputs


def _build_help_entry(header: str, description: str, examples: list[str], ways: list[str]) -> dict[str, Any]:
    brief = header.split(" -- ", 1)[1].strip() if " -- " in header else header
    output_values = _extract_output_descriptions(examples)

    input_description = ""
    if ways:
        preview = "; ".join(ways[:12])
        suffix = "; ..." if len(ways) > 12 else ""
        input_description = f"Accepted call forms: {preview}{suffix}"

    output_description = ""
    if output_values:
        output_description = f"Example outputs: {'; '.join(output_values[:6])}"

    return {
        "brief": brief,
        "description": description,
        "examples": examples,
        "ways": ways,
        "inputDescription": input_description,
        "outputDescription": output_description,
    }


def parse_help_payload(raw: str) -> dict[str, Any]:
    text = decode_external_string(raw)
    if "M2HELP2|HEADER=" not in text:
        return {}

    lines = text.splitlines()
    header = ""
    description_lines: list[str] = []
    examples: list[str] = []
    ways: list[str] = []
    method_payloads: dict[str, dict[str, Any]] = {}

    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("M2HELP2|HEADER="):
            header = line.split("=", 1)[1]
            index += 1
            continue
        if line == "M2HELP2|DESCRIPTION_BEGIN":
            index += 1
            while index < len(lines) and lines[index] != "M2HELP2|DESCRIPTION_END":
                description_lines.append(lines[index])
                index += 1
            index += 1
            continue
        if line == "M2HELP2|EXAMPLE_BEGIN":
            block: list[str] = []
            index += 1
            while index < len(lines) and lines[index] != "M2HELP2|EXAMPLE_END":
                block.append(lines[index])
                index += 1
            examples.append("\n".join(block))
            index += 1
            continue
        if line.startswith("M2HELP2|WAYS_ITEM="):
            ways.append(_unquote_way_item(line.split("=", 1)[1]))
            index += 1
            continue
        if line.startswith("M2HELP2|METHOD_BEGIN="):
            signature_id = line.split("=", 1)[1].strip()
            method_header = ""
            method_description_lines: list[str] = []
            method_examples: list[str] = []
            method_ways: list[str] = []
            index += 1
            while index < len(lines):
                method_line = lines[index]
                if method_line == "M2HELP2|METHOD_END":
                    method_payloads[signature_id] = _build_help_entry(
                        method_header.strip(),
                        "\n".join(method_description_lines).strip(),
                        [item for item in method_examples if item.strip()],
                        [item for item in method_ways if item],
                    )
                    index += 1
                    break
                if method_line.startswith("M2HELP2|METHOD_HEADER="):
                    method_header = method_line.split("=", 1)[1]
                    index += 1
                    continue
                if method_line == "M2HELP2|METHOD_DESCRIPTION_BEGIN":
                    index += 1
                    while index < len(lines) and lines[index] != "M2HELP2|METHOD_DESCRIPTION_END":
                        method_description_lines.append(lines[index])
                        index += 1
                    index += 1
                    continue
                if method_line == "M2HELP2|METHOD_EXAMPLE_BEGIN":
                    block: list[str] = []
                    index += 1
                    while index < len(lines) and lines[index] != "M2HELP2|METHOD_EXAMPLE_END":
                        block.append(lines[index])
                        index += 1
                    method_examples.append("\n".join(block))
                    index += 1
                    continue
                if method_line.startswith("M2HELP2|METHOD_WAYS_ITEM="):
                    method_ways.append(_unquote_way_item(method_line.split("=", 1)[1]))
                    index += 1
                    continue
                index += 1
            continue
        index += 1

    description = "\n".join(description_lines).strip()
    top = _build_help_entry(
        header.strip(),
        description,
        [example for example in examples if example.strip()],
        [way for way in ways if way],
    )
    top["header"] = header.strip()
    top["methods"] = method_payloads
    return top


def parse_help_text(symbol: str, raw: str) -> dict[str, Any]:
    if not raw:
        return {}

    payload = parse_help_payload(raw)
    header = payload.get("header", "")
    if not header:
        return {}

    first_word = header.split()[0]
    if first_word != symbol:
        return {}

    return {
        "brief": payload.get("brief", ""),
        "description": payload.get("description", ""),
        "examples": payload.get("examples", []),
        "inputDescription": payload.get("inputDescription", ""),
        "outputDescription": payload.get("outputDescription", ""),
        "methods": payload.get("methods", {}),
    }


def normalize(records: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    by_symbol: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        by_symbol[record["symbol"]][record["probe"]] = record

    objects: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    reverse_index: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    known_type_names: set[str] = set()
    known_type_details: dict[str, dict[str, Any]] = {}
    emitted_object_ids: set[str] = set()

    def register_type(type_name: str) -> None:
        normalized = type_name.strip()
        if not normalized or normalized == "Nothing":
            return
        known_type_names.add(normalized)

    for symbol in sorted(by_symbol, key=str.casefold):
        probes = by_symbol[symbol]
        runtime_class = probes.get("runtime_class", {}).get("stdout")
        symbol_class = probes.get("symbol_class", {}).get("stdout")
        kind = classify_kind(symbol, runtime_class, symbol_class)
        object_id = canonical_id(kind, symbol)
        function_payload: dict[str, Any] | None = None
        function_input_ids: set[str] = set()

        methods = parse_methods(probes.get("methods", {}).get("stdout", ""))
        option_symbols = parse_options(probes.get("options", {}).get("stdout", ""))
        help_info = parse_help_text(symbol, probes.get("help_text", {}).get("stdout", ""))
        help_methods = help_info.get("methods", {})

        methods = [method for method in methods if not method["signature_id"].startswith("(")]
        if kind == "operator" and help_methods:
            methods = []

        methods_by_signature = {method["signature_id"]: method for method in methods}
        for signature_id in help_methods:
            if signature_id in methods_by_signature:
                continue
            parsed_method = parse_signature_id(signature_id)
            if parsed_method is not None:
                methods_by_signature[signature_id] = parsed_method
        methods = [methods_by_signature[key] for key in sorted(methods_by_signature, key=str.casefold)]

        if kind == "type":
            register_type(symbol)
            known_type_details[symbol] = {
                "brief": help_info.get("brief") or probes.get("to_string", {}).get("stdout", "") or symbol,
                "description": help_info.get("description", ""),
                "type": runtime_class or "Type",
                "examples": help_info.get("examples", []),
                "parent": probes.get("parent", {}).get("stdout") or None,
            }
            parent_name = probes.get("parent", {}).get("stdout")
            if parent_name:
                register_type(parent_name)

        object_record = {
            "id": object_id,
            "name": symbol,
            "kind": kind,
            "brief": help_info.get("brief") or probes.get("to_string", {}).get("stdout", ""),
            "description": help_info.get("description", ""),
            "type": runtime_class or "Unknown",
            "examples": help_info.get("examples", []),
            "function": None,
            "operator": {
                "operatorForm": "unknown",
                "precedence": None,
                "installable": None,
                "augmentedAssignmentForms": [],
                "surfaceName": symbol,
                "canonicalId": object_id,
            }
            if kind == "operator"
            else None,
            "introspection": {probe: probes[probe].get("stdout", "") for probe in probes},
        }

        if kind in {"function", "operator"}:
            function_payload = {
                "inputs": [],
                "outputs": [],
                "inputDescription": help_info.get("inputDescription", ""),
                "outputDescription": help_info.get("outputDescription", ""),
                "options": [canonical_id("symbol", opt) for opt in option_symbols],
                "installedMethods": [],
                "typicalValue": None,
                "dispatch": "runtime",
            }
            object_record["function"] = function_payload

        if kind == "type":
            object_record["parent"] = probes.get("parent", {}).get("stdout") or None

        for method in methods:
            method_id = canonical_id("method", method["signature_id"])
            method_help = help_methods.get(method["signature_id"], {})
            method_record = {
                "id": method_id,
                "name": method["signature"],
                "kind": "method",
                "brief": method_help.get("brief") or method["signature"],
                "description": method_help.get("description", ""),
                "type": "InstalledMethod",
                "examples": method_help.get("examples", []),
                "signature": method["signature"],
                "inputDescription": method_help.get("inputDescription", ""),
                "outputDescription": method_help.get("outputDescription", ""),
                "dispatch": {
                    "function": object_id,
                    "inputs": [canonical_id("type", value) for value in method["inputs"]],
                    "outputs": [],
                },
            }
            objects.append(method_record)

            relations.append({"from": object_id, "to": method_id, "type": "has_method"})
            reverse_index[object_id]["methods"].append(method_id)
            reverse_index[method_id]["function"].append(object_id)

            for input_type in method["inputs"]:
                register_type(input_type)
                type_id = canonical_id("type", input_type)
                relations.append({"from": method_id, "to": type_id, "type": "input_type"})
                reverse_index[type_id]["usableByMethods"].append(method_id)

                if function_payload is not None and type_id not in function_input_ids:
                    function_payload["inputs"].append({"type": type_id, "description": ""})
                    function_input_ids.add(type_id)

            if function_payload is not None:
                function_payload["installedMethods"].append(method_id)

        for option_symbol in option_symbols:
            option_id = canonical_id("symbol", option_symbol)
            relations.append({"from": object_id, "to": option_id, "type": "accepts_option_symbol"})
            reverse_index[option_id]["usedBy"].append(object_id)

        objects.append(object_record)
        emitted_object_ids.add(object_id)

    for type_name in sorted(known_type_names, key=str.casefold):
        type_id = canonical_id("type", type_name)
        details = known_type_details.get(type_name)
        if details is None:
            details = {
                "brief": type_name,
                "description": "",
                "type": "Type",
                "examples": [],
                "parent": None,
            }

        if type_id not in emitted_object_ids:
            type_record = {
                "id": type_id,
                "name": type_name,
                "kind": "type",
                "brief": details["brief"],
                "description": details["description"],
                "type": details["type"],
                "examples": details["examples"],
                "parent": details["parent"],
                "introspection": {},
            }
            objects.append(type_record)
            emitted_object_ids.add(type_id)

        parent_name = details.get("parent")
        if isinstance(parent_name, str) and parent_name and parent_name != "Nothing":
            parent_id = canonical_id("type", parent_name)
            relations.append({"from": type_id, "to": parent_id, "type": "parent_type"})
            reverse_index[parent_id]["children"].append(type_id)

    objects = sorted(objects, key=lambda item: (item["kind"], item["name"].casefold()))
    relations = sorted(relations, key=lambda edge: (edge["type"], edge["from"], edge["to"]))
    index = {
        "reverse": {
            key: {field: sorted(set(values)) for field, values in fields.items()}
            for key, fields in reverse_index.items()
        }
    }

    meta = {
        "schemaVersion": "1.0.0",
        "library": "Core",
        "objectCount": len(objects),
        "relationCount": len(relations),
    }
    return {"meta": meta, "objects": objects}, {"meta": meta, "relations": relations}, index


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/core/raw/latest.jsonl", help="Input JSONL path")
    parser.add_argument(
        "--objects-output",
        default="data/core/normalized/objects.json",
        help="Normalized objects output path",
    )
    parser.add_argument(
        "--relations-output",
        default="data/core/normalized/relations.json",
        help="Relations output path",
    )
    parser.add_argument(
        "--index-output",
        default="data/core/index/reverse.json",
        help="Reverse index output path",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: input does not exist: {input_path}", file=sys.stderr)
        return 1

    records = read_jsonl(input_path)
    objects, relations, index = normalize(records)
    write_json(Path(args.objects_output), objects)
    write_json(Path(args.relations_output), relations)
    write_json(Path(args.index_output), index)
    print(
        "Wrote normalized outputs:",
        args.objects_output,
        args.relations_output,
        args.index_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
