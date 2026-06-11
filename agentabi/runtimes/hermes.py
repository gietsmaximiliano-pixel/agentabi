"""Adapter for the Hermes Agent runtime layout."""

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
            config, error = load_structured(config_path)
            if error or not isinstance(config, dict):
                components.append(
                    make_component(
                        Category.RUNTIME_CONFIG,
                        "hermes.yaml",
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
                        root, config_path, config, "hermes.yaml", identity_key="identity"
                    )
                )
        schedules_path = root / "schedules.yaml"
        if schedules_path.is_file():
            data, error = load_structured(schedules_path)
            jobs = data.get("jobs") if isinstance(data, dict) else None
            if error or not isinstance(jobs, list):
                components.append(
                    make_component(
                        Category.CRON,
                        "schedules.yaml",
                        root,
                        schedules_path,
                        confidence=0.3,
                        warnings=[error or "unknown schema: expected a 'jobs' list"],
                    )
                )
            else:
                components.extend(job_components(root, schedules_path, jobs, "deliver_to"))
        hooks_path = root / "hooks.yaml"
        if hooks_path.is_file():
            data, error = load_structured(hooks_path)
            hooks = data.get("hooks") if isinstance(data, dict) else None
            if error or not isinstance(hooks, list):
                components.append(
                    make_component(
                        Category.HOOK,
                        "hooks.yaml",
                        root,
                        hooks_path,
                        confidence=0.3,
                        warnings=[error or "unknown schema: expected a 'hooks' list"],
                    )
                )
            else:
                components.extend(hook_components(root, hooks_path, hooks))
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
                skill_name = path.parent.name if path.stem == "skill" else path.stem
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
