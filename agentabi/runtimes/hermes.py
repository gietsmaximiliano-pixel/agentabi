"""Adapter for the Hermes Agent runtime layout."""

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


class HermesAdapter(RuntimeAdapter):
    """Normalizes a Hermes Agent state directory."""

    name = "hermes"

    def detect(self, root: Path) -> float:
        score = 0.0
        if (root / "hermes.yaml").is_file():
            score += 0.8
        if (root / "state" / "memory").is_dir():
            score += 0.1
        if (root / "identity").is_dir():
            score += 0.1
        return min(score, 1.0)

    def scan(self, root: Path, files: list[Path]) -> list[Component]:
        components: list[Component] = []
        required: set[str] = set()
        config_path = root / "hermes.yaml"
        if config_path.is_file():
            cfg_components, required = load_runtime_config(
                root, config_path, "hermes.yaml", identity_key="identity"
            )
            components.extend(cfg_components)
        schedules_path = root / "schedules.yaml"
        if schedules_path.is_file():
            jobs, warn = load_list_or_warn(
                root,
                schedules_path,
                "schedules.yaml",
                Category.CRON,
                key="jobs",
                error_hint="a 'jobs' list",
            )
            if jobs is not None:
                components.extend(job_components(root, schedules_path, jobs, "deliver_to"))
            elif warn:
                components.append(warn)
        hooks_path = root / "hooks.yaml"
        if hooks_path.is_file():
            hooks, warn = load_list_or_warn(
                root,
                hooks_path,
                "hooks.yaml",
                Category.HOOK,
                key="hooks",
                error_hint="a 'hooks' list",
            )
            if hooks is not None:
                components.extend(hook_components(root, hooks_path, hooks))
            elif warn:
                components.append(warn)
        for path in files:
            relative = path.relative_to(root).as_posix()
            if relative.startswith("identity/") and path.suffix == ".md":
                components.append(make_component(Category.CONTEXT, path.name, root, path))
            elif relative.startswith("state/memory/") and path.suffix == ".md":
                components.append(
                    make_component(
                        Category.MEMORY, relative.removeprefix("state/memory/"), root, path
                    )
                )
            elif relative.startswith("skills/") and path.suffix in {".yaml", ".yml"}:
                skill_name = skill_name_from_path(path, sentinel_stem="skill")
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
