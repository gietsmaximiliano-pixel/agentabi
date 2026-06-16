"""Secret-file detection, metadata redaction, and bounded safe traversal."""

from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REDACTED = "[REDACTED]"

SECRET_FILE_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "auth.json",
    "credentials.json",
    "secrets.*",
    "tokens.*",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "*.jks",
    "*.keystore",
    "*.gpg",
    "*.asc",
    "id_rsa",
    "id_rsa.*",
    "id_ed25519",
    "id_ed25519.*",
    "id_ecdsa",
    "id_ecdsa.*",
    "id_dsa",
    "id_dsa.*",
    "private*",
    "credential*",
    "password*",
    "cookie*",
    "vault*",
    ".htpasswd",
    ".netrc",
    ".pgpass",
    "*.keyring",
    "service-account*.json",
    "*-credentials.json",
)

SENSITIVE_KEY_PARTS: tuple[str, ...] = (
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "credential",
    "cookie",
    "bearer",
    "private_key",
    "access_key",
    "refresh_token",
    "client_secret",
    "webhook",
    "auth_token",
    "session_id",
    "session_key",
    "signing_key",
    "encryption_key",
    "passphrase",
    "service_account",
    "connection_string",
    "database_url",
)

MAX_DEPTH = 12
MAX_FILES = 5000
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MiB


def is_secret_filename(name: str) -> bool:
    """Return True when *name* matches a known secret-file pattern."""
    lowered = name.lower()
    return any(fnmatch.fnmatch(lowered, pattern) for pattern in SECRET_FILE_PATTERNS)


def is_sensitive_key(key: str) -> bool:
    """Return True when a mapping key looks like it holds sensitive data."""
    normalized = key.lower().replace("-", "_")
    collapsed = normalized.replace("_", "")
    return any(
        part in normalized or part.replace("_", "") in collapsed for part in SENSITIVE_KEY_PARTS
    )


def redact(value: Any, depth: int = 0) -> Any:
    """Recursively redact sensitive keys in mappings and sequences."""
    if depth > 32:
        return REDACTED
    if isinstance(value, dict):
        return {
            key: REDACTED if is_sensitive_key(str(key)) else redact(item, depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, depth + 1) for item in value]
    return value


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(category: str, name: str, path: str) -> str:
    """Return a short, deterministic identifier for a component."""
    raw = f"{category}:{name}:{path}".encode()
    return hashlib.sha256(raw, usedforsecurity=False).hexdigest()[:12]


@dataclass
class WalkResult:
    """Outcome of a bounded, symlink-safe directory walk."""

    files: list[Path] = field(default_factory=list)
    secret_files: list[tuple[str, int]] = field(default_factory=list)
    symlinks_skipped: int = 0
    unreadable: int = 0
    truncated: bool = False
    notes: list[str] = field(default_factory=list)


def _within(resolved_root: Path, target: Path) -> bool:
    try:
        return target.resolve().is_relative_to(resolved_root)
    except OSError:
        return False


def safe_walk(root: Path, *, max_depth: int = MAX_DEPTH, max_files: int = MAX_FILES) -> WalkResult:
    """Deterministically walk *root* without escaping it through symlinks."""
    result = WalkResult()
    resolved_root = root.resolve()
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            result.truncated = True
            result.notes.append(f"max depth reached under {current.name}; scan incomplete")
            continue
        try:
            entries = sorted(current.iterdir(), key=lambda entry: entry.name)
        except OSError:
            result.unreadable += 1
            continue
        for entry in entries:
            if len(result.files) >= max_files:
                result.truncated = True
                result.notes.append("max file count reached; scan incomplete")
                result.files.sort(key=lambda item: item.relative_to(root).as_posix())
                return result
            if entry.is_symlink() and not _within(resolved_root, entry):
                result.symlinks_skipped += 1
                continue
            if entry.is_dir():
                stack.append((entry, depth + 1))
                continue
            if not entry.is_file():
                continue
            relative = entry.relative_to(root).as_posix()
            if is_secret_filename(entry.name):
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = -1
                result.secret_files.append((relative, size))
                continue
            result.files.append(entry)
    result.files.sort(key=lambda item: item.relative_to(root).as_posix())
    result.secret_files.sort()
    return result
