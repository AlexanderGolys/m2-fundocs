# m2-fundocs

Remake Macaulay2 documentation for Core builtins with a data-first pipeline.

## Goal

Build a structured, machine-readable knowledge base for Macaulay2 Core objects by:

1. Collecting introspection output from the Macaulay2 CLI
2. Normalizing the output into stable JSON schemas
3. Using the data for LSP features and a web documentation renderer

## Current Status

- Repository scaffolding is in progress
- Initial Python-based extraction + normalization scripts are available
- Agent instructions are in `AGENTS.md`

## Planned Data Flow

1. Enumerate Core symbols
2. Run introspection probes per symbol
3. Persist raw captures for provenance
4. Normalize into canonical JSON objects
5. Sort deterministically and export artifacts for LSP/web

## Development Notes

- Keep transforms deterministic
- Preserve raw source output before parsing
- Attach provenance metadata to derived fields

## Quick Start

Collect a small sample:

```bash
python3 tools/m2_collect.py --symbol ideal --symbol matrix
python3 tools/m2_normalize.py
```

Run tests:

```bash
python3 -m unittest
```

Run a single test module:

```bash
python3 -m unittest tests.test_normalize
```

View normalized results:

```bash
python3 tools/m2_view.py summary
python3 tools/m2_view.py list --kind function --limit 20
python3 tools/m2_view.py show core::function::ideal
```

Documentation references:

- `M2_COMMANDS.md`
- `docs/INTROSPECTION_REFERENCE.md`
