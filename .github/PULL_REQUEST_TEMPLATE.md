## What does this PR do?

## Checklist

- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `mypy agentabi` passes
- [ ] `pytest --cov=agentabi` passes; new rules have positive and negative tests
- [ ] Fixtures added/changed are fully synthetic (no real credentials or personal data)
- [ ] Core invariants preserved: offline, deterministic, read-only, secret-safe
- [ ] CHANGELOG.md updated if user-facing

## Related issues
