"""Tests for secret safety, redaction, hashing, and bounded traversal."""

from __future__ import annotations

import os

import pytest

from agentabi.security import (
    is_secret_filename,
    is_sensitive_key,
    redact,
    safe_walk,
    sha256_file,
    stable_id,
)


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        ".env.production",
        "auth.json",
        "credentials.json",
        "secrets.yaml",
        "tokens.json",
        "server.pem",
        "tls.key",
        "cert.pfx",
        "keystore.p12",
        "app.jks",
        "trust.keystore",
        "key.gpg",
        "private.asc",
        "id_rsa",
        "id_rsa.pub",
        "id_ed25519",
        "id_ed25519.pub",
        "id_ecdsa",
        "id_ecdsa.pub",
        "id_dsa",
        "id_dsa.pub",
        "private_notes.txt",
        "credential-cache.db",
        "passwords.txt",
        "cookies.sqlite",
        "vault.bin",
        ".htpasswd",
        ".netrc",
        ".pgpass",
        "login.keyring",
        "service-account-key.json",
        "gcp-credentials.json",
    ],
)
def test_secret_filenames_detected(name):
    assert is_secret_filename(name)


@pytest.mark.parametrize("name", ["README.md", "openclaw.json", "core.md", "schedules.yaml"])
def test_regular_filenames_allowed(name):
    assert not is_secret_filename(name)


@pytest.mark.parametrize(
    "key",
    [
        "token",
        "API_KEY",
        "apiKey",
        "client_secret",
        "webhook_url",
        "refresh-token",
        "Password",
        "passwd",
        "auth_token",
        "session_id",
        "SESSION_KEY",
        "signing_key",
        "encryption_key",
        "passphrase",
        "service_account",
        "connection_string",
        "DATABASE_URL",
    ],
)
def test_sensitive_keys(key):
    assert is_sensitive_key(key)


def test_redact_nested():
    data = {
        "model": "synthetic",
        "api_key": "leak",
        "nested": {"refresh_token": "leak", "safe": 1},
        "items": [{"client_secret": "leak"}, "plain"],
    }
    redacted = redact(data)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["refresh_token"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == 1
    assert redacted["items"][0]["client_secret"] == "[REDACTED]"
    assert redacted["items"][1] == "plain"
    assert redacted["model"] == "synthetic"


def test_stable_id_deterministic():
    first = stable_id("memory", "core.md", "memory/core.md")
    assert first == stable_id("memory", "core.md", "memory/core.md")
    assert len(first) == 12
    assert first != stable_id("memory", "core.md", "elsewhere/core.md")


def test_sha256_file(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("agentabi", encoding="utf-8")
    assert sha256_file(path) == sha256_file(path)
    assert len(sha256_file(path)) == 64


def test_safe_walk_skips_secret_files(tmp_path):
    (tmp_path / ".env").write_text("TOKEN=x", encoding="utf-8")
    (tmp_path / "note.md").write_text("hello", encoding="utf-8")
    result = safe_walk(tmp_path)
    assert [item.name for item in result.files] == ["note.md"]
    assert result.secret_files == [(".env", 7)]


def test_safe_walk_never_escapes_root(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret-data.txt").write_text("outside", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    (root / "inside.md").write_text("inside", encoding="utf-8")
    try:
        os.symlink(outside, root / "escape")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    result = safe_walk(root)
    assert [item.name for item in result.files] == ["inside.md"]
    assert result.symlinks_skipped == 1


def test_safe_walk_file_limit(tmp_path):
    for index in range(10):
        (tmp_path / f"file-{index}.md").write_text("x", encoding="utf-8")
    result = safe_walk(tmp_path, max_files=5)
    assert result.truncated
    assert len(result.files) <= 5


def test_safe_walk_depth_limit(tmp_path):
    current = tmp_path
    for index in range(6):
        current = current / f"level-{index}"
    current.mkdir(parents=True)
    (current / "deep.md").write_text("deep", encoding="utf-8")
    result = safe_walk(tmp_path, max_depth=3)
    assert result.truncated
    assert result.files == []
