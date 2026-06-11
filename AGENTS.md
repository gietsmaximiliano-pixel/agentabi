# AGENTS.md

Guidance for AI coding agents working on this repository.

## Project

AgentABI is a local-first, read-only compatibility checker for persistent AI-agent
state. Core invariants that must never be broken:

1. **Offline**: no network requests anywhere in `agentabi/`.
2. **Deterministic**: no timestamps, randomness, or environment-dependent output
   in manifests or reports.
3. **Read-only**: scanned input directories are never modified.
4. **Secret-safe**: secret files are never opened (see `agentabi/security.py`);
   sensitive metadata keys are redacted.

## Layout

- `agentabi/models.py` - Pydantic v2 models (strict, `extra="forbid"`).
- `agentabi/security.py` - secret patterns, redaction, bounded safe walk.
- `agentabi/runtimes/` - one adapter per runtime + auto-detection registry.
- `agentabi/scanner.py` - walk + adapter orchestration into a `Manifest`.
- `agentabi/compare.py` - diff rules producing `Finding`s.
- `agentabi/scoring.py` - score and recommendation.
- `agentabi/report.py` - terminal/JSON/Markdown rendering.
- `agentabi/cli.py` - Typer CLI (`snapshot`, `diff`, `verify`, `doctor`, `demo`).
- `tests/fixtures/` - fully synthetic fixtures only.

## Commands

```bash
python -m pip install -e ".[dev]"
ruff check . && ruff format --check .
mypy agentabi
pytest --cov=agentabi --cov-report=term-missing
python -m build && twine check dist/*
agentabi demo
```

## Rules for changes

- Every new comparison rule needs a positive and a negative test.
- New fixtures must be synthetic; never include real credentials, even fake-looking ones.
- Keep exit-code semantics: 0 = ok, 1 = threshold exceeded, 2 = usage/input error.
- Do not add Claude Code support in 0.1.x; it is roadmap-only.
