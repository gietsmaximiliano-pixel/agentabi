"""Integration tests for all CLI commands and exit codes."""

from __future__ import annotations

import json
import shutil

from typer.testing import CliRunner

from agentabi.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("snapshot", "diff", "verify", "doctor", "demo"):
        assert command in result.output


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_snapshot_json(fixtures_dir):
    result = runner.invoke(app, ["snapshot", str(fixtures_dir / "openclaw_healthy"), "--json"])
    assert result.exit_code == 0
    manifest = json.loads(result.output)
    assert manifest["runtime"] == "openclaw"
    assert manifest["components"]


def test_snapshot_out_file(fixtures_dir, tmp_path):
    out = tmp_path / "manifest.json"
    result = runner.invoke(
        app, ["snapshot", str(fixtures_dir / "hermes_healthy"), "--out", str(out)]
    )
    assert result.exit_code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["runtime"] == "hermes"


def test_snapshot_invalid_runtime(fixtures_dir):
    result = runner.invoke(
        app, ["snapshot", str(fixtures_dir / "openclaw_healthy"), "--runtime", "bogus"]
    )
    assert result.exit_code == 2


def test_snapshot_missing_directory(tmp_path):
    result = runner.invoke(app, ["snapshot", str(tmp_path / "missing")])
    assert result.exit_code == 2


def _manifests(fixtures_dir, tmp_path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    runner.invoke(app, ["snapshot", str(fixtures_dir / "openclaw_healthy"), "--out", str(before)])
    runner.invoke(app, ["snapshot", str(fixtures_dir / "hermes_broken"), "--out", str(after)])
    return before, after


def test_diff_exit_codes(fixtures_dir, tmp_path):
    before, after = _manifests(fixtures_dir, tmp_path)
    assert runner.invoke(app, ["diff", str(before), str(after)]).exit_code == 1
    assert (
        runner.invoke(app, ["diff", str(before), str(after), "--fail-on", "none"]).exit_code == 0
    )
    assert (
        runner.invoke(app, ["diff", str(before), str(before), "--fail-on", "warning"]).exit_code
        == 0
    )


def test_diff_score_only(fixtures_dir, tmp_path):
    before, after = _manifests(fixtures_dir, tmp_path)
    result = runner.invoke(
        app, ["diff", str(before), str(after), "--score-only", "--fail-on", "none"]
    )
    assert result.exit_code == 0
    assert result.output.strip() == "20"


def test_diff_json_and_markdown(fixtures_dir, tmp_path):
    before, after = _manifests(fixtures_dir, tmp_path)
    markdown_path = tmp_path / "report.md"
    result = runner.invoke(
        app,
        [
            "diff",
            str(before),
            str(after),
            "--json",
            "--markdown",
            str(markdown_path),
            "--fail-on",
            "none",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["recommendation"] == "DO NOT DEPLOY"
    assert "# AgentABI Compatibility Report" in markdown_path.read_text(encoding="utf-8")


def test_diff_rejects_bad_manifest(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert runner.invoke(app, ["diff", str(bad), str(bad)]).exit_code == 2


def test_verify_healthy(fixtures_dir, tmp_path):
    out_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "verify",
            "--source",
            str(fixtures_dir / "openclaw_healthy"),
            "--candidate",
            str(fixtures_dir / "hermes_healthy"),
            "--out-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0
    for name in ("source.manifest.json", "candidate.manifest.json", "report.json", "report.md"):
        assert (out_dir / name).is_file()


def test_verify_breaking_fails(fixtures_dir):
    result = runner.invoke(
        app,
        [
            "verify",
            "--source",
            str(fixtures_dir / "openclaw_healthy"),
            "--candidate",
            str(fixtures_dir / "hermes_broken"),
        ],
    )
    assert result.exit_code == 1
    assert "DO NOT DEPLOY" in result.output


def test_verify_json(fixtures_dir):
    result = runner.invoke(
        app,
        [
            "verify",
            "--source",
            str(fixtures_dir / "openclaw_healthy"),
            "--candidate",
            str(fixtures_dir / "hermes_healthy"),
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.output)["score"] == 100


def test_verify_invalid_runtime(fixtures_dir):
    result = runner.invoke(
        app,
        [
            "verify",
            "--source",
            str(fixtures_dir / "openclaw_healthy"),
            "--candidate",
            str(fixtures_dir / "hermes_healthy"),
            "--from",
            "bogus",
        ],
    )
    assert result.exit_code == 2


def test_doctor(fixtures_dir):
    result = runner.invoke(app, ["doctor", str(fixtures_dir / "openclaw_healthy")])
    assert result.exit_code == 0
    assert "openclaw" in result.output


def test_doctor_json_malformed(fixtures_dir):
    result = runner.invoke(app, ["doctor", str(fixtures_dir / "malformed_state"), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["runtime"] == "openclaw"
    assert payload["warnings"]


def test_demo():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "DO NOT DEPLOY" in result.output


def test_verify_does_not_modify_inputs(fixtures_dir, tmp_path, tree_digest):
    source = tmp_path / "source"
    candidate = tmp_path / "candidate"
    shutil.copytree(fixtures_dir / "openclaw_healthy", source)
    shutil.copytree(fixtures_dir / "hermes_broken", candidate)
    digests = (tree_digest(source), tree_digest(candidate))
    runner.invoke(
        app,
        [
            "verify",
            "--source",
            str(source),
            "--candidate",
            str(candidate),
            "--fail-on",
            "none",
        ],
    )
    assert (tree_digest(source), tree_digest(candidate)) == digests
