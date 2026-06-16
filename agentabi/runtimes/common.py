"""Shared helpers for runtime adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from agentabi.models import Category, Component
from agentabi.security import MAX_FILE_SIZE, redact, sha256_file, stable_id


def load_structured(path: Path) -> tuple[Any, str | None]:
    """Load a JSON or YAML file, returning ``(data, error)``."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"unreadable: {exc.__class__.__name__}"
    except UnicodeDecodeError:
        return None, "unreadable: not valid UTF-8"
    try:
        if path.suffix == ".json":
            return json.loads(text), None
        return yaml.safe_load(text), None
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        return None, f"unknown schema: {exc}"


def safe_digest(path: Path) -> tuple[str | None, str | None]:
    """Hash a file when it is small enough and readable.

    Returns ``(digest, warning)``.
    """
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return None, f"file exceeds size limit ({MAX_FILE_SIZE} bytes); digest skipped"
        return sha256_file(path), None
    except OSError as exc:
        return None, f"could not hash file: {exc}"


def make_component(
    category: Category,
    name: str,
    root: Path,
    path: Path | None,
    *,
    metadata: dict[str, Any] | None = None,
    evidence: list[str] | None = None,
    confidence: float = 1.0,
    warnings: list[str] | None = None,
    digest: bool = True,
) -> Component:
    """Build a normalized component with a stable id and redacted metadata."""
    relative = path.relative_to(root).as_posix() if path is not None else ""
    component_digest = None
    digest_warning = None
    if digest and path is not None and path.is_file():
        component_digest, digest_warning = safe_digest(path)
    all_warnings = list(warnings or [])
    if digest_warning:
        all_warnings.append(digest_warning)
    return Component(
        id=stable_id(category.value, name, relative),
        category=category,
        name=name,
        path=relative,
        digest=component_digest,
        metadata=redact(metadata or {}),
        evidence=evidence or ([relative] if relative else []),
        confidence=confidence,
        warnings=all_warnings,
    )


def config_components(
    root: Path,
    config_path: Path,
    config: dict[str, Any],
    config_name: str,
    *,
    identity_key: str,
) -> list[Component]:
    """Normalize runtime config, tool policy, MCP servers, and channels."""
    components = [
        make_component(
            Category.RUNTIME_CONFIG,
            config_name,
            root,
            config_path,
            metadata={"identity": config.get(identity_key) or {}, "model": config.get("model")},
        )
    ]
    tools = config.get("tools")
    if isinstance(tools, dict):
        components.append(
            make_component(Category.TOOL_POLICY, "tools", root, config_path, metadata=dict(tools))
        )
    mcp = config.get("mcp")
    servers = mcp.get("servers") if isinstance(mcp, dict) else None
    if isinstance(servers, dict):
        for server_name in sorted(servers):
            spec = servers[server_name] if isinstance(servers[server_name], dict) else {}
            env = spec.get("env")
            components.append(
                make_component(
                    Category.MCP,
                    str(server_name),
                    root,
                    config_path,
                    metadata={
                        "command": spec.get("command"),
                        "args": [str(item) for item in spec.get("args") or []],
                        "env_keys": sorted(str(key) for key in env)
                        if isinstance(env, dict)
                        else [],
                    },
                )
            )
    channels = config.get("channels")
    if isinstance(channels, dict):
        for channel_name in sorted(channels):
            spec = channels[channel_name] if isinstance(channels[channel_name], dict) else {}
            components.append(
                make_component(
                    Category.CHANNEL,
                    str(channel_name),
                    root,
                    config_path,
                    metadata={"enabled": bool(spec.get("enabled", True)), "kind": spec.get("kind")},
                )
            )
    return components


def job_components(root: Path, path: Path, jobs: list[Any], delivery_key: str) -> list[Component]:
    """Normalize cron jobs and their delivery targets."""
    components: list[Component] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_name = str(job.get("name") or job.get("id") or "unnamed-job")
        raw_delivery = job.get(delivery_key)
        delivery = raw_delivery if isinstance(raw_delivery, dict) else None
        components.append(
            make_component(
                Category.CRON,
                job_name,
                root,
                path,
                metadata={
                    "schedule": job.get("schedule"),
                    "enabled": bool(job.get("enabled", True)),
                    "has_delivery": delivery is not None,
                },
            )
        )
        if delivery is not None:
            channel = str(delivery.get("channel", "unknown"))
            components.append(
                make_component(
                    Category.DELIVERY_TARGET,
                    f"{job_name}:{channel}",
                    root,
                    path,
                    metadata={"channel": channel, "job": job_name},
                )
            )
    return components


def hook_components(root: Path, path: Path, hooks: list[Any]) -> list[Component]:
    """Normalize event hooks."""
    components: list[Component] = []
    for hook in hooks:
        if not isinstance(hook, dict):
            continue
        hook_name = str(hook.get("name") or "unnamed-hook")
        events = hook.get("events") or hook.get("event") or []
        if isinstance(events, str):
            events = [events]
        components.append(
            make_component(
                Category.HOOK,
                hook_name,
                root,
                path,
                metadata={
                    "events": sorted(str(event) for event in events),
                    "scope": hook.get("scope"),
                    "enabled": bool(hook.get("enabled", True)),
                },
            )
        )
    return components


# ---------------------------------------------------------------------------
# Shared high-level loading helpers used by multiple runtime adapters
# ---------------------------------------------------------------------------


def load_runtime_config(
    root: Path,
    config_path: Path,
    config_name: str,
    *,
    identity_key: str,
) -> tuple[list[Component], set[str]]:
    """Load a runtime config, returning normalized components and required skill names.

    On parse failure the returned list contains a single warning component and
    the required-skills set is empty.
    """
    config, error = load_structured(config_path)
    if error or not isinstance(config, dict):
        return [
            make_component(
                Category.RUNTIME_CONFIG,
                config_name,
                root,
                config_path,
                confidence=0.3,
                warnings=[error or "unknown schema: expected a mapping"],
            )
        ], set()
    required = {str(item) for item in config.get("required_skills") or []}
    return (
        config_components(root, config_path, config, config_name, identity_key=identity_key),
        required,
    )


def load_list_or_warn(
    root: Path,
    path: Path,
    name: str,
    category: Category,
    *,
    key: str | None = None,
    error_hint: str = "a list",
) -> tuple[list[Any] | None, Component | None]:
    """Load a structured file and extract a list.

    Returns ``(items, None)`` on success or ``(None, warning_component)`` on
    failure.  When *key* is given the loaded data is expected to be a mapping
    and ``data[key]`` is used as the list.
    """
    data, error = load_structured(path)
    items: Any = data
    if key is not None:
        items = data.get(key) if isinstance(data, dict) else None
    if error or not isinstance(items, list):
        return None, make_component(
            category,
            name,
            root,
            path,
            confidence=0.3,
            warnings=[error or f"unknown schema: expected {error_hint}"],
        )
    return items, None


def skill_name_from_path(path: Path, *, sentinel_stem: str) -> str:
    """Derive a skill name from its file path.

    If the file stem matches *sentinel_stem* the parent directory name is used;
    otherwise the stem itself is the skill name.
    """
    if path.stem == sentinel_stem:
        return path.parent.name
    return path.stem
