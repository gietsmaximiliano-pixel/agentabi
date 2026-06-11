"""Directory scanning and manifest construction."""

from __future__ import annotations

from pathlib import Path

from agentabi import __version__
from agentabi.models import Category, Component, Manifest, ScanStats
from agentabi.runtimes import detect_runtime, get_adapter
from agentabi.security import safe_walk, stable_id


class ScanError(ValueError):
    """Raised when a state directory cannot be scanned."""


def snapshot(root: Path, runtime: str = "auto") -> Manifest:
    """Scan *root* (read-only) and build a normalized manifest."""
    if not root.is_dir():
        raise ScanError(f"not a directory: {root}")
    if runtime == "auto":
        runtime_name, confidence = detect_runtime(root)
    else:
        runtime_name, confidence = runtime, 1.0
    walk = safe_walk(root)
    components = list(get_adapter(runtime_name).scan(root, walk.files))
    for relative, size in walk.secret_files:
        components.append(
            Component(
                id=stable_id(Category.SECRET_FILE.value, relative, relative),
                category=Category.SECRET_FILE,
                name=relative,
                path=relative,
                digest=None,
                metadata={"size_bytes": size},
                evidence=[relative],
                confidence=1.0,
                warnings=["secret file detected; contents were never read"],
            )
        )
    components.sort(
        key=lambda component: (component.category.value, component.name, component.path)
    )
    stats = ScanStats(
        files_seen=len(walk.files) + len(walk.secret_files),
        files_hashed=sum(1 for component in components if component.digest),
        secret_files_skipped=len(walk.secret_files),
        symlinks_skipped=walk.symlinks_skipped,
        unreadable_files=walk.unreadable,
        truncated=walk.truncated,
        notes=list(walk.notes),
    )
    return Manifest(
        tool_version=__version__,
        runtime=runtime_name,
        runtime_confidence=round(confidence, 2),
        root_label=root.name,
        components=components,
        stats=stats,
    )
