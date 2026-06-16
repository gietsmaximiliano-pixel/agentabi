"""Tests for runtimes/common.py: load_structured, safe_digest, job/hook edge cases."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from agentabi.models import Category
from agentabi.runtimes.common import (
    hook_components,
    job_components,
    load_structured,
    safe_digest,
)
from agentabi.security import MAX_FILE_SIZE


def test_load_structured_json(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text('{"key": 1}', encoding="utf-8")
    data, error = load_structured(path)
    assert data == {"key": 1}
    assert error is None


def test_load_structured_yaml(tmp_path: Path) -> None:
    path = tmp_path / "data.yaml"
    path.write_text("key: 1\n", encoding="utf-8")
    data, error = load_structured(path)
    assert data == {"key": 1}
    assert error is None


def test_load_structured_oserror(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    data, error = load_structured(path)
    assert data is None
    assert error is not None and "unreadable" in error


def test_load_structured_unicode_error(tmp_path: Path) -> None:
    path = tmp_path / "binary.json"
    path.write_bytes(b"\xff\xfe")
    data, error = load_structured(path)
    assert data is None
    assert error is not None and "not valid UTF-8" in error


def test_load_structured_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{bad", encoding="utf-8")
    data, error = load_structured(path)
    assert data is None
    assert error is not None and "unknown schema" in error


def test_load_structured_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(":\n  - :\n  - :\n  [bad", encoding="utf-8")
    data, error = load_structured(path)
    assert data is None
    assert error is not None and "unknown schema" in error


def test_safe_digest_normal_file(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("hello", encoding="utf-8")
    digest, warning = safe_digest(path)
    assert digest is not None
    assert len(digest) == 64
    assert warning is None


def test_safe_digest_large_file(tmp_path: Path) -> None:
    path = tmp_path / "large.bin"
    path.write_bytes(b"\x00" * (MAX_FILE_SIZE + 1))
    digest, warning = safe_digest(path)
    assert digest is None
    assert warning is not None and "size limit" in warning


def test_safe_digest_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"
    digest, warning = safe_digest(path)
    assert digest is None
    assert warning is not None


def test_safe_digest_oserror_on_stat(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("data", encoding="utf-8")
    with patch.object(Path, "stat", side_effect=OSError("boom")):
        digest, warning = safe_digest(path)
        assert digest is None
        assert warning is not None


def test_job_components_skips_non_dict(tmp_path: Path) -> None:
    root = tmp_path
    path = root / "jobs.json"
    path.write_text("[]", encoding="utf-8")
    jobs: list[Any] = ["not-a-dict", 42, None]
    result = job_components(root, path, jobs, "delivery")
    assert result == []


def test_job_components_with_delivery(tmp_path: Path) -> None:
    root = tmp_path
    path = root / "jobs.json"
    path.write_text("[]", encoding="utf-8")
    jobs: list[Any] = [
        {
            "name": "test-job",
            "schedule": "0 9 * * *",
            "enabled": True,
            "delivery": {"channel": "email"},
        }
    ]
    result = job_components(root, path, jobs, "delivery")
    assert len(result) == 2
    cron = [c for c in result if c.category is Category.CRON]
    delivery = [c for c in result if c.category is Category.DELIVERY_TARGET]
    assert len(cron) == 1
    assert cron[0].name == "test-job"
    assert len(delivery) == 1
    assert delivery[0].name == "test-job:email"


def test_hook_components_skips_non_dict(tmp_path: Path) -> None:
    root = tmp_path
    path = root / "hooks.json"
    path.write_text("[]", encoding="utf-8")
    hooks: list[Any] = ["not-a-dict", 42]
    result = hook_components(root, path, hooks)
    assert result == []


def test_hook_components_events_as_string(tmp_path: Path) -> None:
    root = tmp_path
    path = root / "hooks.yaml"
    path.write_text("[]", encoding="utf-8")
    hooks: list[Any] = [{"name": "on-commit", "event": "commit", "scope": "repo", "enabled": True}]
    result = hook_components(root, path, hooks)
    assert len(result) == 1
    assert result[0].category is Category.HOOK
    assert result[0].name == "on-commit"
    assert result[0].metadata["events"] == ["commit"]


def test_hook_components_events_as_list(tmp_path: Path) -> None:
    root = tmp_path
    path = root / "hooks.yaml"
    path.write_text("[]", encoding="utf-8")
    hooks: list[Any] = [{"name": "watcher", "events": ["push", "pull"], "enabled": True}]
    result = hook_components(root, path, hooks)
    assert len(result) == 1
    assert result[0].metadata["events"] == ["pull", "push"]
