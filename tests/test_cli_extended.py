"""Extended CLI tests: verbose snapshot, verbose doctor, no-issues doctor."""

from __future__ import annotations

from typer.testing import CliRunner

from agentabi.cli import app

runner = CliRunner()


def test_snapshot_verbose(fixtures_dir):
    result = runner.invoke(app, ["snapshot", str(fixtures_dir / "openclaw_healthy"), "--verbose"])
    assert result.exit_code == 0
    assert "Runtime:" in result.output
    assert "Components:" in result.output
    assert "reporter" in result.output
    assert "research" in result.output


def test_doctor_verbose(fixtures_dir):
    result = runner.invoke(app, ["doctor", str(fixtures_dir / "openclaw_healthy"), "--verbose"])
    assert result.exit_code == 0
    assert "Components discovered:" in result.output
    assert "reporter" in result.output or "core.md" in result.output


def test_doctor_no_issues(fixtures_dir):
    result = runner.invoke(app, ["doctor", str(fixtures_dir / "openclaw_healthy")])
    assert result.exit_code == 0
    assert "No problems detected" in result.output


def test_diff_verbose(fixtures_dir, tmp_path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    runner.invoke(app, ["snapshot", str(fixtures_dir / "openclaw_healthy"), "--out", str(before)])
    runner.invoke(app, ["snapshot", str(fixtures_dir / "hermes_broken"), "--out", str(after)])
    result = runner.invoke(
        app,
        ["diff", str(before), str(after), "--verbose", "--fail-on", "none"],
    )
    assert result.exit_code == 0
    assert "Component Comparison" in result.output or "Limitations" in result.output
