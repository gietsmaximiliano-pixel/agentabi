# Contributing to AgentABI

Thanks for your interest in contributing!

## Development setup

```bash
git clone <your-fork>
cd agentabi
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Validation

Run the full check suite before opening a pull request:

```bash
ruff check .
ruff format --check .
mypy agentabi
pytest --cov=agentabi --cov-report=term-missing
python -m build
twine check dist/*
agentabi demo
```

## Guidelines

- Keep AgentABI **offline, deterministic, and read-only**. Never add code that
  reads secret-file contents, performs network requests, or mutates scanned input.
- New comparison rules need tests demonstrating both the triggering and the
  non-triggering case.
- New runtime adapters belong in `agentabi/runtimes/` and must ship synthetic
  fixtures under `tests/fixtures/`. Fixtures must be fully synthetic and free of
  any real credentials or personal data.
- Use Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, ...).

## Reporting bugs and requesting features

Please use the issue templates. For security issues, follow [SECURITY.md](SECURITY.md)
instead of opening a public issue.
