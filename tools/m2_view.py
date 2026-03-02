#!/usr/bin/env python3
"""View normalized Macaulay2 Core extraction results."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_OBJECTS = Path("data/core/normalized/objects.json")
DEFAULT_RELATIONS = Path("data/core/normalized/relations.json")
DEFAULT_INDEX = Path("data/core/index/reverse.json")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_indexes(objects: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obj in objects:
        by_id[obj["id"]] = obj
        by_name[obj["name"]].append(obj)
    return by_id, by_name


def resolve_target(
    query: str,
    by_id: dict[str, dict[str, Any]],
    by_name: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if query in by_id:
        return by_id[query]

    candidates = by_name.get(query, [])
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        ids = ", ".join(item["id"] for item in candidates)
        raise ValueError(f"ambiguous name '{query}', use id instead: {ids}")
    raise KeyError(f"object not found: {query}")


def summarize(objects: list[dict[str, Any]], relations: list[dict[str, Any]]) -> dict[str, Any]:
    kind_counts = Counter(item.get("kind", "unknown") for item in objects)
    relation_counts = Counter(edge.get("type", "unknown") for edge in relations)
    mapped_counts = {
        "description": 0,
        "examples": 0,
        "functionInputDescription": 0,
        "functionOutputDescription": 0,
        "methodInputDescription": 0,
        "methodOutputDescription": 0,
    }

    mapped_by_kind: dict[str, dict[str, int]] = defaultdict(lambda: {"description": 0, "examples": 0, "total": 0})
    for item in objects:
        kind = item.get("kind", "unknown")
        mapped_by_kind[kind]["total"] += 1
        if item.get("description"):
            mapped_counts["description"] += 1
            mapped_by_kind[kind]["description"] += 1
        if item.get("examples"):
            mapped_counts["examples"] += 1
            mapped_by_kind[kind]["examples"] += 1

        function_payload = item.get("function")
        if isinstance(function_payload, dict):
            if function_payload.get("inputDescription"):
                mapped_counts["functionInputDescription"] += 1
            if function_payload.get("outputDescription"):
                mapped_counts["functionOutputDescription"] += 1

        if item.get("kind") == "method":
            if item.get("inputDescription"):
                mapped_counts["methodInputDescription"] += 1
            if item.get("outputDescription"):
                mapped_counts["methodOutputDescription"] += 1

    return {
        "objects": len(objects),
        "relations": len(relations),
        "kinds": dict(sorted(kind_counts.items())),
        "relationTypes": dict(sorted(relation_counts.items())),
        "mapped": mapped_counts,
        "mappedByKind": dict(sorted(mapped_by_kind.items())),
    }


def build_show_payload(
    target: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    relations: list[dict[str, Any]],
    reverse: dict[str, Any],
) -> dict[str, Any]:
    target_id = target["id"]
    outgoing = [edge for edge in relations if edge["from"] == target_id]
    incoming = [edge for edge in relations if edge["to"] == target_id]

    method_context: dict[str, Any] | None = None
    if target.get("kind") == "method":
        dispatch = target.get("dispatch") or {}
        function_id = dispatch.get("function")
        input_type_ids = dispatch.get("inputs") or []
        output_type_ids = dispatch.get("outputs") or []

        method_context = {
            "function": by_id.get(function_id) if isinstance(function_id, str) else None,
            "inputTypes": [by_id[type_id] for type_id in input_type_ids if type_id in by_id],
            "outputTypes": [by_id[type_id] for type_id in output_type_ids if type_id in by_id],
            "docs": {
                "brief": target.get("brief", ""),
                "description": target.get("description", ""),
                "examples": target.get("examples", []),
                "inputDescription": target.get("inputDescription", ""),
                "outputDescription": target.get("outputDescription", ""),
            },
        }

    return {
        "object": target,
        "methodContext": method_context,
        "relations": {
            "outgoing": outgoing,
            "incoming": incoming,
            "reverseIndex": reverse.get(target_id, {}),
        },
    }


def cmd_summary(args: argparse.Namespace) -> int:
    objects_payload = load_json(Path(args.objects))
    relations_payload = load_json(Path(args.relations))
    summary = summarize(objects_payload["objects"], relations_payload["relations"])
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    objects_payload = load_json(Path(args.objects))
    objects = objects_payload["objects"]

    filtered = [obj for obj in objects if args.kind is None or obj.get("kind") == args.kind]
    for obj in filtered[: args.limit]:
        print(f"{obj['id']}\t{obj['kind']}\t{obj['name']}")
    print(f"\nShown {min(len(filtered), args.limit)} of {len(filtered)} object(s)")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    objects_payload = load_json(Path(args.objects))
    relations_payload = load_json(Path(args.relations))
    index_payload = load_json(Path(args.index))

    objects = objects_payload["objects"]
    relations = relations_payload["relations"]
    reverse = index_payload.get("reverse", {})
    by_id, by_name = build_indexes(objects)
    target = resolve_target(args.target, by_id, by_name)

    payload = build_show_payload(target, by_id, relations, reverse)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _format_method_report(payload: dict[str, Any]) -> str:
    obj = payload["object"]
    context = payload.get("methodContext") or {}
    docs = context.get("docs") or {}
    function_obj = context.get("function")
    input_types = context.get("inputTypes") or []
    output_types = context.get("outputTypes") or []

    lines = [
        f"Method: {obj.get('id', '')}",
        f"Signature: {obj.get('name', '')}",
        f"Brief: {docs.get('brief', '')}",
        f"Function: {function_obj.get('id') if isinstance(function_obj, dict) else ''}",
        f"Input types: {', '.join(item.get('name', '') for item in input_types) if input_types else '(none)'}",
        f"Output types: {', '.join(item.get('name', '') for item in output_types) if output_types else '(none)'}",
        f"Input description: {docs.get('inputDescription', '')}",
        f"Output description: {docs.get('outputDescription', '')}",
        "",
        "Description:",
        docs.get("description", "") or "(none)",
        "",
        f"Examples ({len(docs.get('examples', []))}):",
    ]
    examples = docs.get("examples", [])
    if examples:
        for index, example in enumerate(examples, start=1):
            lines.append(f"[{index}]")
            lines.append(example)
    else:
        lines.append("(none)")
    return "\n".join(lines)


def cmd_method(args: argparse.Namespace) -> int:
    objects_payload = load_json(Path(args.objects))
    relations_payload = load_json(Path(args.relations))
    index_payload = load_json(Path(args.index))

    objects = objects_payload["objects"]
    relations = relations_payload["relations"]
    reverse = index_payload.get("reverse", {})
    by_id, by_name = build_indexes(objects)
    target = resolve_target(args.target, by_id, by_name)
    if target.get("kind") != "method":
        raise ValueError(f"target is not a method: {target['id']}")

    payload = build_show_payload(target, by_id, relations, reverse)
    print(_format_method_report(payload))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", default=str(DEFAULT_OBJECTS), help="Path to objects.json")
    parser.add_argument("--relations", default=str(DEFAULT_RELATIONS), help="Path to relations.json")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="Path to reverse index JSON")

    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser("summary", help="Show high-level counts")
    summary_parser.set_defaults(handler=cmd_summary)

    list_parser = subparsers.add_parser("list", help="List objects")
    list_parser.add_argument("--kind", help="Filter by kind")
    list_parser.add_argument("--limit", type=int, default=30, help="Maximum rows to print")
    list_parser.set_defaults(handler=cmd_list)

    show_parser = subparsers.add_parser("show", help="Show object details and links")
    show_parser.add_argument("target", help="Object id or exact object name")
    show_parser.set_defaults(handler=cmd_show)

    method_parser = subparsers.add_parser("method", help="Show method-focused docs and dispatch")
    method_parser.add_argument("target", help="Method id or exact method name")
    method_parser.set_defaults(handler=cmd_method)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
