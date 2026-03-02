# AGENTS Guide for `m2-fundocs`

This file is for agentic coding agents working in this repository.
It documents the current project state plus conventions to follow as the codebase grows.

## Repository Snapshot

- Core scripts are in `tools/` (`m2_collect.py`, `m2_normalize.py`).
- Tests are in `tests/` using Python `unittest`.
- No package-level build config is present (`Makefile`, `justfile`, `package.json`, `pyproject.toml`, and `Cargo.toml` are absent).
- No dedicated lint/formatter config is configured yet.
- No Cursor rules were found (`.cursorrules`, `.cursor/rules/` not present).
- No Copilot instructions were found (`.github/copilot-instructions.md` not present).

## Primary Objective Context

- Project direction (from user intent): remake Macaulay2 documentation for Core builtins.
- Expected workflow: introspect M2 builtins via CLI, normalize outputs, and store structured JSON.
- Intended consumers: LSP features and web documentation renderer.

## Commands: Build / Lint / Test

Current commands are script-driven and Python-standard-library based.

### Current Status Commands

- Verify repository state: `git status --short`
- Show repo files: `ls -la`
- Confirm no test/build config exists: `ls -la .`

### Build Commands

- Full collection and normalization run:
  `python3 tools/m2_collect.py && python3 tools/m2_normalize.py`
- Collect selected symbols only:
  `python3 tools/m2_collect.py --symbol ideal --symbol matrix`
- Normalize existing raw JSONL:
  `python3 tools/m2_normalize.py --input data/core/raw/latest.jsonl`
- View normalized summaries:
  `python3 tools/m2_view.py summary`

### Lint Commands

- Current: no lint tool configured.
- Baseline syntax check for Python scripts:
  `python3 -m py_compile tools/m2_collect.py tools/m2_normalize.py tests/test_normalize.py`
- If Ruff/Black (or alternatives) are added, update this section with exact commands.

### Test Commands

- Run all tests:
  `python3 -m unittest`
- Run verbose tests:
  `python3 -m unittest -v`

### Single-Test Guidance (when tests are introduced)

Current single-test commands (`unittest`):

- Single test module: `python3 -m unittest tests.test_normalize`
- Single test case: `python3 -m unittest tests.test_normalize.NormalizeTests.test_parse_methods_extracts_signatures`

If framework changes later (e.g., pytest), replace this section with canonical commands.

## Agent Workflow Rules

- Read repository reality first; do not assume missing infrastructure.
- Keep changes minimal, explicit, and reversible.
- Prefer adding foundational scaffolding over speculative complexity.
- For new scripts, include usage/help text and deterministic outputs.
- For documentation/data generation, keep runs reproducible.

## Code Style Baseline

These standards apply until language-specific configs are committed.

### General

- Prefer clear, short, self-documenting code.
- Favor pure functions and small modules where practical.
- Avoid hidden side effects and global mutable state.
- Add comments only for non-obvious decisions, not obvious mechanics.
- Keep functions focused; split long functions by responsibility.

### Naming

- Use descriptive names; avoid abbreviations unless domain-standard.
- Functions: verb or verb phrase (`collect_symbols`, `parse_signature`).
- Types/classes: nouns (`BuiltinObject`, `MethodSignature`).
- Constants: uppercase with underscores (`MAX_RETRIES`).
- Files: consistent lowercase naming (`collector.py`, `normalize.ts`).

### Imports / Dependencies

- Keep imports grouped: standard library, third-party, local.
- Remove unused imports.
- Avoid circular imports; refactor shared utilities instead.
- Prefer explicit imports over wildcard imports.
- Keep dependency footprint small and justified.

### Formatting

- Use formatter-default style once a formatter is introduced.
- Keep lines readable (target <= 100 chars unless language tooling differs).
- Use consistent indentation and trailing newline at EOF.
- Do not mix formatting styles in same file.

### Types and Data Modeling

- Use explicit types where supported (TypeScript types, Python type hints, Rust types).
- Avoid untyped dictionary blobs for core schema objects.
- Define stable schema structs/interfaces for generated JSON.
- Distinguish required vs optional fields clearly.
- Version serialized schema (`schemaVersion`) from the beginning.

### Error Handling

- Fail loudly for programmer errors (invalid invariants, bad assumptions).
- Return structured errors for expected runtime failures.
- Include actionable context in error messages (symbol, file, command).
- Avoid swallowing exceptions without logging/context.
- Prefer one consistent error strategy per language.

### Logging and Diagnostics

- Keep logs concise and machine-readable when possible.
- Include enough context to reproduce failures.
- Separate user-facing output from debug output.
- Do not print secrets or sensitive paths/tokens.

## Data Pipeline Conventions (for M2 docs generation)

- Preserve raw introspection output before normalization.
- Attach provenance metadata to derived fields.
- Keep normalization deterministic (same input => same output).
- Sort generated records deterministically (e.g., by `kind`, then `name`).
- Avoid lossy transforms unless explicitly documented.
- Validate output schema before writing final JSON.

## Documentation Standards

- Update docs in same change when behavior/commands change.
- Prefer concrete examples over vague prose.
- Keep this file current when tooling is added.
- If Cursor/Copilot rule files are later added, summarize them here.
- Keep `docs/INTROSPECTION_REFERENCE.md` updated when probes or source pages change.

## Git Hygiene for Agents

- Do not revert unrelated user changes.
- Keep commits scoped and descriptive.
- Run available checks before committing (when they exist).
- If checks do not exist yet, state what you validated manually.

## Future TODO (once project scaffolding is added)

- Add richer build orchestration command (single entrypoint script/Make target).
- Add explicit lint command(s) with autofix variant.
- Expand tests from parser unit tests to integration tests against sample raw data.
- Add schema validation command for generated JSON.
- Add CI command parity section (local vs CI).

## Quick Update Checklist for Agents

When you add or change tooling, update this file in the same PR:

- Build command added/changed
- Lint command added/changed
- Test command added/changed
- Single-test command verified
- Formatter/type checker command documented
- Any Cursor/Copilot instructions reflected
