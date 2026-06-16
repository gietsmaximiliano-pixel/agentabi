"""Extended tests for security.py: deep redaction, _within OSError, safe_walk edge cases."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from agentabi.security import REDACTED, redact, safe_walk


def test_redact_exceeds_depth_limit() -> None:
    value: dict[str, object] = {"safe": "ok"}
    current: dict[str, object] = value
    for _ in range(35):
        inner: dict[str, object] = {"nested": "data"}
        current["child"] = inner
        current = inner
    result = redact(value)
    assert result["safe"] == "ok"
    walk: object = result
    for _ in range(33):
        assert isinstance(walk, dict)
        walk = walk["child"]
    assert walk == REDACTED


def test_safe_walk_unreadable_directory(tmp_path: Path) -> None:
    unreadable = tmp_path / "noperm"
    unreadable.mkdir()
    (tmp_path / "visible.txt").write_text("hi", encoding="utf-8")
    unreadable.chmod(0o000)
    try:
        result = safe_walk(tmp_path)
        assert result.unreadable >= 1
        assert any(f.name == "visible.txt" for f in result.files)
    finally:
        unreadable.chmod(0o755)


def test_safe_walk_skips_non_regular_files(tmp_path: Path) -> None:
    fifo_path = tmp_path / "pipe"
    (tmp_path / "regular.txt").write_text("ok", encoding="utf-8")
    try:
        os.mkfifo(fifo_path)
    except (OSError, AttributeError):
        pytest.skip("FIFOs not supported on this platform")
    result = safe_walk(tmp_path)
    names = [f.name for f in result.files]
    assert "regular.txt" in names
    assert "pipe" not in names


def test_safe_walk_secret_file_stat_error(tmp_path: Path) -> None:
    secret = tmp_path / ".env"
    secret.write_text("SECRET=val", encoding="utf-8")
    original_stat = Path.stat
    call_count: dict[str, int] = {}

    def _stat_that_fails(self: Path, **kwargs: object) -> os.stat_result:
        if self.name == ".env":
            call_count[".env"] = call_count.get(".env", 0) + 1
            # Fail on the 4th+ call (after is_symlink/lstat, is_dir, is_file)
            if call_count[".env"] >= 4:
                raise OSError("synthetic stat failure")
        return original_stat(self, **kwargs)

    with patch.object(Path, "stat", _stat_that_fails):
        result = safe_walk(tmp_path)
    matched = [s for s in result.secret_files if s[0] == ".env"]
    assert len(matched) == 1
    assert matched[0][1] == -1


def test_safe_walk_symlink_within_root(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    target = sub / "target.txt"
    target.write_text("content", encoding="utf-8")
    try:
        os.symlink(sub, tmp_path / "link_to_sub")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    result = safe_walk(tmp_path)
    names = [f.name for f in result.files]
    assert "target.txt" in names
    assert result.symlinks_skipped == 0
