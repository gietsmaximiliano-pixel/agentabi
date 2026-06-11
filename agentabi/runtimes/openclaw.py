"""Adapter for the OpenClaw agent runtime layout."""

from __future__ import annotations

from pathlib import Path

from agentabi.models import Category, Component
from agentabi.runtimes.base import RuntimeAdapter
from agentabi.runtimes.common import (
    config_components,
    hook_components,
    job_components,
    load_structured,
    make_component,
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
            config, error = load_structured(config_path)
            if error or not isinstance(config, dict):
                components.append(
                    make_component(
                        Category.RUNTIME_CONFIG,
                        "openclaw.json",
                        root,
                        config_path,
                        confidence=0.3,
                        warnings=[error or "unknown schema: expected a mapping"],
                    )
                )
            else:
                required = {str(item) for item in config.get("required_skills") or []}
                components.extend(
                    config_components(
                        root, config_path, config, "openclaw.json", identity_key="agent"
                    )
                )
        jobs_path = root / "cron" / "jobs.json"
        if jobs_path.is_file():
            data, error = load_structured(jobs_path)
            if error or not isinstance(data, list):
                components.append(
                    make_component(
                        Category.CRON,
                        "jobs.json",
                        root,
                        jobs_path,
                        confidence=0.3,
                        warnings=[error or "unknown schema: expected a list of jobs"],
                    )
                )
            else:
                components.extend(job_components(root, jobs_path, data, "delivery"))
        hooks_path = root / "hooks" / "hooks.json"
        if hooks_path.is_file():
            data, error = load_structured(hooks_path)
            if error or not isinstance(data, list):
                components.append(
                    make_component(
                        Category.HOOK,
                        "hooks.json",
                        root,
                        hooks_path,
                        confidence=0.3,
                        warnings=[error or "unknown schema: expected a list of hooks"],
                    )
                )
            else:
                components.extend(hook_components(root, hooks_path, data))
        for path in files:
            relative = path.relative_to(root).as_posix()
            if path.parent == root and path.name in CONTEXT_FILES:
                components.append(make_component(Category.CONTEXT, path.name, root, path))
            elif relative.startswith("memory/") and path.suffix == ".md":
                components.append(
                    make_component(
                        Category.MEMORY, relative.removeprefix("memory/"), root, path
                    )
                )
            elif relative.startswith("skills/") and path.suffix == ".md":
                skill_name = path.parent.name if path.name == "SKILL.md" else path.stem
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
