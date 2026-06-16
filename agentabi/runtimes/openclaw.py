"""Adapter for the OpenClaw agent runtime layout."""

from __future__ import annotations

from pathlib import Path

from agentabi.models import Category, Component
from agentabi.runtimes.base import RuntimeAdapter
from agentabi.runtimes.common import (
    hook_components,
    job_components,
    load_list_or_warn,
    load_runtime_config,
    make_component,
    skill_name_from_path,
)

CONTEXT_FILES = ("AGENT.md", "SOUL.md", "IDENTITY.md")


class OpenClawAdapter(RuntimeAdapter):
    """Normalizes an OpenClaw state directory."""

    name = "openclaw"

    def detect(self, root: Path) -> float:
        score = 0.0
        if (root / "openclaw.json").is_file():
            score += 0.8
        if (root / "memory").is_dir():
            score += 0.1
        if any((root / item).is_file() for item in CONTEXT_FILES):
            score += 0.1
        return min(score, 1.0)

    def scan(self, root: Path, files: list[Path]) -> list[Component]:
        components: list[Component] = []
        required: set[str] = set()
        config_path = root / "openclaw.json"
        if config_path.is_file():
            cfg_components, required = load_runtime_config(
                root, config_path, "openclaw.json", identity_key="agent"
            )
            components.extend(cfg_components)
        jobs_path = root / "cron" / "jobs.json"
        if jobs_path.is_file():
            jobs, warn = load_list_or_warn(
                root,
                jobs_path,
                "jobs.json",
                Category.CRON,
                error_hint="a list of jobs",
            )
            if jobs is not None:
                components.extend(job_components(root, jobs_path, jobs, "delivery"))
            elif warn:
                components.append(warn)
        hooks_path = root / "hooks" / "hooks.json"
        if hooks_path.is_file():
            hooks, warn = load_list_or_warn(
                root,
                hooks_path,
                "hooks.json",
                Category.HOOK,
                error_hint="a list of hooks",
            )
            if hooks is not None:
                components.extend(hook_components(root, hooks_path, hooks))
            elif warn:
                components.append(warn)
        for path in files:
            relative = path.relative_to(root).as_posix()
            if path.parent == root and path.name in CONTEXT_FILES:
                components.append(make_component(Category.CONTEXT, path.name, root, path))
            elif relative.startswith("memory/") and path.suffix == ".md":
                components.append(
                    make_component(Category.MEMORY, relative.removeprefix("memory/"), root, path)
                )
            elif relative.startswith("skills/") and path.suffix == ".md":
                skill_name = skill_name_from_path(path, sentinel_stem="SKILL")
                components.append(
                    make_component(
                        Category.SKILL,
                        skill_name,
                        root,
                        path,
                        metadata={"required": skill_name in required},
                    )
                )
        return components
