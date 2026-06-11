"""Tests for the diff engine, severities, and scoring."""

from __future__ import annotations

from agentabi.compare import compare
from agentabi.models import Category, Component, Finding, Manifest, Severity
from agentabi.scanner import snapshot
from agentabi.scoring import recommend, score


def make_component(category, name, path="config.json", metadata=None, digest=None):
    return Component(
        id=f"{category.value}-{name}",
        category=category,
        name=name,
        path=path,
        digest=digest,
        metadata=metadata or {},
    )


def make_manifest(components, runtime="openclaw"):
    return Manifest(
        tool_version="0.1.0",
        runtime=runtime,
        runtime_confidence=1.0,
        root_label="test",
        components=components,
    )


def test_healthy_migration(fixtures_dir):
    report = compare(
        snapshot(fixtures_dir / "openclaw_healthy"),
        snapshot(fixtures_dir / "hermes_healthy"),
    )
    assert report.findings == []
    assert report.score == 100
    assert report.recommendation == "SAFE TO DEPLOY"


def test_broken_migration(fixtures_dir):
    report = compare(
        snapshot(fixtures_dir / "openclaw_healthy"),
        snapshot(fixtures_dir / "hermes_broken"),
    )
    ids = {finding.id for finding in report.findings}
    assert "memory-all-missing" in ids
    assert "skill-missing:reporter" in ids
    assert "delivery-missing:daily-report:telegram" in ids
    assert "mcp-command:search" in ids
    assert "channel-missing:telegram" in ids
    assert report.recommendation == "DO NOT DEPLOY"
    assert report.score == 20


def test_broadened_permissions(fixtures_dir):
    report = compare(
        snapshot(fixtures_dir / "openclaw_healthy"),
        snapshot(fixtures_dir / "hermes_broader_permissions"),
    )
    ids = {finding.id for finding in report.findings}
    assert {"isolation-weakened", "tools-broadened", "shell-unrestricted"} <= ids
    assert report.recommendation == "DO NOT DEPLOY"


def test_duplicate_skill_names():
    before = make_manifest([make_component(Category.SKILL, "research", "skills/research.md")])
    after = make_manifest(
        [
            make_component(Category.SKILL, "research", "skills/research.md"),
            Component(
                id="dup",
                category=Category.SKILL,
                name="research",
                path="skills/research/SKILL.md",
            ),
        ]
    )
    report = compare(before, after)
    assert any(
        finding.id == "skill-duplicate:research" and finding.severity is Severity.BREAKING
        for finding in report.findings
    )


def test_memory_count_drop():
    before = make_manifest(
        [make_component(Category.MEMORY, f"m{i}.md", f"memory/m{i}.md") for i in range(4)]
    )
    after = make_manifest(
        [make_component(Category.MEMORY, f"m{i}.md", f"memory/m{i}.md") for i in range(2)]
    )
    report = compare(before, after)
    ids = {finding.id for finding in report.findings}
    assert "memory-count-drop" in ids
    assert "memory-missing:m2.md" in ids


def test_cron_schedule_change():
    before = make_manifest(
        [
            make_component(
                Category.CRON, "daily", metadata={"schedule": "0 9 * * *", "enabled": True}
            )
        ]
    )
    after = make_manifest(
        [
            make_component(
                Category.CRON, "daily", metadata={"schedule": "*/5 * * * *", "enabled": True}
            )
        ]
    )
    report = compare(before, after)
    assert any(
        finding.id == "cron-schedule:daily" and finding.severity is Severity.HIGH
        for finding in report.findings
    )


def test_hook_scope_broadened():
    before = make_manifest(
        [make_component(Category.HOOK, "h", metadata={"events": ["a"], "enabled": True})]
    )
    after = make_manifest(
        [make_component(Category.HOOK, "h", metadata={"events": ["a", "b"], "enabled": True})]
    )
    report = compare(before, after)
    assert any(finding.id == "hook-broadened:h" for finding in report.findings)


def test_relocation_same_runtime_only():
    before = make_manifest([make_component(Category.CONTEXT, "AGENT.md", "AGENT.md")])
    after_same = make_manifest([make_component(Category.CONTEXT, "AGENT.md", "ctx/AGENT.md")])
    report = compare(before, after_same)
    assert any(finding.id.startswith("relocated:") for finding in report.findings)
    after_cross = make_manifest(
        [make_component(Category.CONTEXT, "AGENT.md", "identity/AGENT.md")], runtime="hermes"
    )
    report_cross = compare(before, after_cross)
    assert not any(finding.id.startswith("relocated:") for finding in report_cross.findings)


def test_score_clamped_and_recommendation():
    breaking = [
        Finding(
            id=f"b{i}",
            severity=Severity.BREAKING,
            category=Category.MEMORY,
            title="t",
            detail="d",
        )
        for i in range(6)
    ]
    assert score(breaking) == 0
    assert recommend(breaking) == "DO NOT DEPLOY"
    assert score([]) == 100
    assert recommend([]) == "SAFE TO DEPLOY"
    warning = [
        Finding(id="w", severity=Severity.WARNING, category=Category.SKILL, title="t", detail="d")
    ]
    assert score(warning) == 97
    assert recommend(warning) == "DEPLOY WITH CAUTION"
