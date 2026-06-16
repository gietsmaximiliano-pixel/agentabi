"""Extended tests for compare.py: MCP, skill digest, schema, scan, and removal edge cases."""

from __future__ import annotations

from agentabi.compare import compare
from agentabi.models import Category, Component, Manifest, Severity


def _component(
    category: Category,
    name: str,
    path: str = "config.json",
    metadata: dict | None = None,
    digest: str | None = None,
    warnings: list[str] | None = None,
) -> Component:
    return Component(
        id=f"{category.value}-{name}",
        category=category,
        name=name,
        path=path,
        digest=digest,
        metadata=metadata or {},
        warnings=warnings or [],
    )


def _manifest(
    components: list[Component],
    runtime: str = "openclaw",
    truncated: bool = False,
) -> Manifest:
    m = Manifest(
        tool_version="0.1.0",
        runtime=runtime,
        runtime_confidence=1.0,
        root_label="test",
        components=components,
    )
    if truncated:
        m.stats.truncated = True
        m.stats.notes.append("max depth reached; scan incomplete")
    return m


def test_mcp_args_changed() -> None:
    before = _manifest(
        [
            _component(
                Category.MCP,
                "search",
                metadata={"command": "npx", "args": ["--port", "8080"], "env_keys": []},
            )
        ]
    )
    after = _manifest(
        [
            _component(
                Category.MCP,
                "search",
                metadata={"command": "npx", "args": ["--port", "9090"], "env_keys": []},
            )
        ]
    )
    report = compare(before, after)
    ids = {f.id for f in report.findings}
    assert "mcp-args:search" in ids
    finding = next(f for f in report.findings if f.id == "mcp-args:search")
    assert finding.severity is Severity.WARNING


def test_mcp_env_keys_changed() -> None:
    before = _manifest(
        [
            _component(
                Category.MCP,
                "db",
                metadata={"command": "pg", "args": [], "env_keys": ["DB_URL"]},
            )
        ]
    )
    after = _manifest(
        [
            _component(
                Category.MCP,
                "db",
                metadata={"command": "pg", "args": [], "env_keys": ["DB_URL", "DB_PASS"]},
            )
        ]
    )
    report = compare(before, after)
    ids = {f.id for f in report.findings}
    assert "mcp-env:db" in ids
    finding = next(f for f in report.findings if f.id == "mcp-env:db")
    assert finding.severity is Severity.WARNING


def test_skill_digest_changed() -> None:
    before = _manifest(
        [
            _component(
                Category.SKILL,
                "research",
                path="skills/research.yaml",
                digest="a" * 64,
            )
        ]
    )
    after = _manifest(
        [
            _component(
                Category.SKILL,
                "research",
                path="skills/research.yaml",
                digest="b" * 64,
            )
        ]
    )
    report = compare(before, after)
    ids = {f.id for f in report.findings}
    assert "skill-digest:research" in ids
    finding = next(f for f in report.findings if f.id == "skill-digest:research")
    assert finding.severity is Severity.WARNING


def test_skill_digest_not_triggered_different_extensions() -> None:
    before = _manifest(
        [
            _component(
                Category.SKILL,
                "research",
                path="skills/research.yaml",
                digest="a" * 64,
            )
        ]
    )
    after = _manifest(
        [
            _component(
                Category.SKILL,
                "research",
                path="skills/research.md",
                digest="b" * 64,
            )
        ]
    )
    report = compare(before, after)
    ids = {f.id for f in report.findings}
    assert "skill-digest:research" not in ids


def test_non_required_skill_absent() -> None:
    before = _manifest(
        [
            _component(
                Category.SKILL,
                "optional-tool",
                path="skills/optional-tool.md",
                metadata={"required": False},
            )
        ]
    )
    after = _manifest([])
    report = compare(before, after)
    ids = {f.id for f in report.findings}
    assert "skill-absent:optional-tool" in ids
    finding = next(f for f in report.findings if f.id == "skill-absent:optional-tool")
    assert finding.severity is Severity.WARNING


def test_disabled_cron_removal_no_finding() -> None:
    before = _manifest(
        [
            _component(
                Category.CRON,
                "disabled-job",
                metadata={"schedule": "0 0 * * *", "enabled": False},
            )
        ]
    )
    after = _manifest([])
    report = compare(before, after)
    ids = {f.id for f in report.findings}
    assert "cron-missing:disabled-job" not in ids


def test_schema_unknown_finding() -> None:
    before = _manifest([])
    after = _manifest(
        [
            _component(
                Category.RUNTIME_CONFIG,
                "openclaw.json",
                path="openclaw.json",
                warnings=["unknown schema: file could not be parsed"],
            )
        ]
    )
    report = compare(before, after)
    ids = {f.id for f in report.findings}
    assert "schema-unknown" in ids


def test_unsupported_components_finding() -> None:
    before = _manifest([])
    after = _manifest([_component(Category.UNKNOWN, "mystery.cfg", path="mystery.cfg")])
    report = compare(before, after)
    ids = {f.id for f in report.findings}
    assert "unsupported-components" in ids


def test_scan_incomplete_finding() -> None:
    before = _manifest([], truncated=True)
    after = _manifest([])
    report = compare(before, after)
    ids = {f.id for f in report.findings}
    assert "scan-incomplete:source" in ids


def test_scan_incomplete_both() -> None:
    before = _manifest([], truncated=True)
    after = _manifest([], truncated=True)
    report = compare(before, after)
    ids = {f.id for f in report.findings}
    assert "scan-incomplete:source" in ids
    assert "scan-incomplete:candidate" in ids
