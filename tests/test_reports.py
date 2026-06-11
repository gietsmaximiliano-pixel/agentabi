"""Tests for JSON and Markdown report rendering."""

from __future__ import annotations

import json

from agentabi.compare import compare
from agentabi.report import to_json, to_markdown
from agentabi.scanner import snapshot


def test_markdown_report(fixtures_dir):
    report = compare(
        snapshot(fixtures_dir / "openclaw_healthy"),
        snapshot(fixtures_dir / "hermes_broken"),
    )
    markdown = to_markdown(report)
    assert "# AgentABI Compatibility Report" in markdown
    assert "## Executive Summary" in markdown
    assert "DO NOT DEPLOY" in markdown
    assert "### BREAKING" in markdown
    assert "## Component Comparison" in markdown
    assert "## Scan Limitations" in markdown
    assert "## Manual-Review Checklist" in markdown
    assert "## Privacy Note" in markdown


def test_json_report(fixtures_dir):
    report = compare(
        snapshot(fixtures_dir / "openclaw_healthy"),
        snapshot(fixtures_dir / "hermes_healthy"),
    )
    payload = json.loads(to_json(report))
    assert payload["score"] == 100
    assert payload["recommendation"] == "SAFE TO DEPLOY"
    assert payload["findings"] == []
    assert "privacy_note" in payload


def test_json_report_deterministic(fixtures_dir):
    first = to_json(
        compare(
            snapshot(fixtures_dir / "openclaw_healthy"),
            snapshot(fixtures_dir / "hermes_broken"),
        )
    )
    second = to_json(
        compare(
            snapshot(fixtures_dir / "openclaw_healthy"),
            snapshot(fixtures_dir / "hermes_broken"),
        )
    )
    assert first == second
