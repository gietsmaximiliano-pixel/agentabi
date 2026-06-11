"""Tests for runtime detection, discovery, normalization, and serialization."""

from __future__ import annotations

import shutil

import pytest

from agentabi.models import Category, Manifest
from agentabi.runtimes import detect_runtime
from agentabi.scanner import ScanError, snapshot


def test_detect_openclaw(fixtures_dir):
    name, confidence = detect_runtime(fixtures_dir / "openclaw_healthy")
    assert name == "openclaw"
    assert confidence >= 0.8


def test_detect_hermes(fixtures_dir):
    name, confidence = detect_runtime(fixtures_dir / "hermes_healthy")
    assert name == "hermes"
    assert confidence >= 0.8


def test_detect_unknown(tmp_path):
    (tmp_path / "random.txt").write_text("hi", encoding="utf-8")
    assert detect_runtime(tmp_path)[0] == "unknown"


def test_snapshot_openclaw_components(fixtures_dir):
    manifest = snapshot(fixtures_dir / "openclaw_healthy")
    by_category: dict[Category, list] = {}
    for component in manifest.components:
        by_category.setdefault(component.category, []).append(component)
    assert {c.name for c in by_category[Category.MEMORY]} == {
        "core.md",
        "2025-01.md",
        "2025-02.md",
    }
    assert {c.name for c in by_category[Category.SKILL]} == {"research", "reporter"}
    assert all(c.metadata["required"] for c in by_category[Category.SKILL])
    assert {c.name for c in by_category[Category.CRON]} == {"daily-report", "weekly-digest"}
    assert {c.name for c in by_category[Category.DELIVERY_TARGET]} == {
        "daily-report:telegram",
        "weekly-digest:email",
    }
    assert {c.name for c in by_category[Category.CHANNEL]} == {"telegram", "email"}
    assert by_category[Category.MCP][0].metadata["command"] == "npx"
    assert by_category[Category.MCP][0].metadata["env_keys"] == ["SEARCH_API_KEY"]
    assert Category.TOOL_POLICY in by_category
    assert Category.CONTEXT in by_category
    assert Category.HOOK in by_category
    assert Category.RUNTIME_CONFIG in by_category


def test_snapshot_is_deterministic(fixtures_dir):
    first = snapshot(fixtures_dir / "openclaw_healthy").model_dump_json()
    second = snapshot(fixtures_dir / "openclaw_healthy").model_dump_json()
    assert first == second


def test_manifest_round_trip(fixtures_dir):
    manifest = snapshot(fixtures_dir / "hermes_healthy")
    restored = Manifest.model_validate_json(manifest.model_dump_json())
    assert restored == manifest


def test_component_digests_are_stable(fixtures_dir):
    manifest = snapshot(fixtures_dir / "openclaw_healthy")
    memory = [c for c in manifest.components if c.category is Category.MEMORY]
    assert memory
    assert all(c.digest and len(c.digest) == 64 for c in memory)


def test_secret_files_never_read(fixtures_dir):
    manifest = snapshot(fixtures_dir / "secrets_state")
    secrets = [c for c in manifest.components if c.category is Category.SECRET_FILE]
    assert sorted(c.name for c in secrets) == [".env", "auth.json", "id_rsa"]
    assert all(c.digest is None for c in secrets)
    assert all(c.metadata["size_bytes"] >= 0 for c in secrets)
    assert manifest.stats.secret_files_skipped == 3
    dump = manifest.model_dump_json()
    assert "do-not-read" not in dump
    assert "NOT A REAL" not in dump


def test_malformed_config_handled(fixtures_dir):
    manifest = snapshot(fixtures_dir / "malformed_state")
    warnings = [w for c in manifest.components for w in c.warnings]
    assert any("unknown schema" in w for w in warnings)


def test_forced_runtime(fixtures_dir):
    manifest = snapshot(fixtures_dir / "openclaw_healthy", "hermes")
    assert manifest.runtime == "hermes"
    assert manifest.runtime_confidence == 1.0


def test_unknown_runtime_marks_unsupported(tmp_path):
    (tmp_path / "mystery.cfg").write_text("data", encoding="utf-8")
    manifest = snapshot(tmp_path)
    assert manifest.runtime == "unknown"
    assert manifest.components
    assert all(c.category is Category.UNKNOWN for c in manifest.components)


def test_snapshot_rejects_missing_directory(tmp_path):
    with pytest.raises(ScanError):
        snapshot(tmp_path / "missing")


def test_inputs_never_modified(fixtures_dir, tmp_path, tree_digest):
    target = tmp_path / "state"
    shutil.copytree(fixtures_dir / "openclaw_healthy", target)
    before = tree_digest(target)
    snapshot(target)
    assert tree_digest(target) == before
