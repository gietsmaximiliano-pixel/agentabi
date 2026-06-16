"""Tests for the Hermes runtime adapter: malformed config, schedules, and hooks."""

from __future__ import annotations

from pathlib import Path

from agentabi.models import Category
from agentabi.runtimes.hermes import HermesAdapter


def _make_hermes_root(tmp_path: Path, config: str | None = None) -> Path:
    root = tmp_path / "hermes_state"
    root.mkdir()
    if config is not None:
        (root / "hermes.yaml").write_text(config, encoding="utf-8")
    return root


def test_malformed_hermes_config(tmp_path: Path) -> None:
    root = _make_hermes_root(tmp_path, config="[bad yaml")
    adapter = HermesAdapter()
    components = adapter.scan(root, [])
    warnings = [w for c in components for w in c.warnings]
    assert any("unknown schema" in w for w in warnings)
    assert components[0].category is Category.RUNTIME_CONFIG


def test_hermes_config_not_a_mapping(tmp_path: Path) -> None:
    root = _make_hermes_root(tmp_path, config="- item1\n- item2\n")
    adapter = HermesAdapter()
    components = adapter.scan(root, [])
    warnings = [w for c in components for w in c.warnings]
    assert any("expected a mapping" in w for w in warnings)


def test_malformed_schedules(tmp_path: Path) -> None:
    root = _make_hermes_root(tmp_path, config="model: test\n")
    schedules = root / "schedules.yaml"
    schedules.write_text("[not a mapping", encoding="utf-8")
    adapter = HermesAdapter()
    components = adapter.scan(root, [])
    cron_warnings = [w for c in components if c.category is Category.CRON for w in c.warnings]
    assert any("unknown schema" in w for w in cron_warnings)


def test_schedules_missing_jobs_key(tmp_path: Path) -> None:
    root = _make_hermes_root(tmp_path, config="model: test\n")
    schedules = root / "schedules.yaml"
    schedules.write_text("other_key: value\n", encoding="utf-8")
    adapter = HermesAdapter()
    components = adapter.scan(root, [])
    cron_components = [c for c in components if c.category is Category.CRON]
    assert len(cron_components) == 1
    assert any("expected a 'jobs' list" in w for w in cron_components[0].warnings)


def test_malformed_hooks(tmp_path: Path) -> None:
    root = _make_hermes_root(tmp_path, config="model: test\n")
    hooks = root / "hooks.yaml"
    hooks.write_text("[broken", encoding="utf-8")
    adapter = HermesAdapter()
    components = adapter.scan(root, [])
    hook_warnings = [w for c in components if c.category is Category.HOOK for w in c.warnings]
    assert any("unknown schema" in w for w in hook_warnings)


def test_hooks_missing_hooks_key(tmp_path: Path) -> None:
    root = _make_hermes_root(tmp_path, config="model: test\n")
    hooks = root / "hooks.yaml"
    hooks.write_text("other: value\n", encoding="utf-8")
    adapter = HermesAdapter()
    components = adapter.scan(root, [])
    hook_components = [c for c in components if c.category is Category.HOOK]
    assert len(hook_components) == 1
    assert any("expected a 'hooks' list" in w for w in hook_components[0].warnings)
