"""Runtime adapters and auto-detection."""

from __future__ import annotations

from pathlib import Path

from agentabi.models import Category, Component
from agentabi.runtimes.base import RuntimeAdapter
from agentabi.runtimes.common import make_component
from agentabi.runtimes.hermes import HermesAdapter
from agentabi.runtimes.openclaw import OpenClawAdapter


class GenericAdapter(RuntimeAdapter):
    """Fallback adapter for unrecognized state directories."""

    name = "unknown"

    def detect(self, root: Path) -> float:
        return 0.0

    def scan(self, root: Path, files: list[Path]) -> list[Component]:
        return [
            make_component(
                Category.UNKNOWN,
                path.relative_to(root).as_posix(),
                root,
                path,
                confidence=0.2,
                warnings=["unsupported component: runtime not recognized"],
            )
            for path in files
        ]


ADAPTERS: dict[str, RuntimeAdapter] = {
    "openclaw": OpenClawAdapter(),
    "hermes": HermesAdapter(),
}
_GENERIC = GenericAdapter()


def detect_runtime(root: Path) -> tuple[str, float]:
    """Return the most likely runtime name and its detection confidence."""
    best_name, best_score = "unknown", 0.0
    for name in sorted(ADAPTERS):
        confidence = ADAPTERS[name].detect(root)
        if confidence > best_score:
            best_name, best_score = name, confidence
    return best_name, best_score


def get_adapter(name: str) -> RuntimeAdapter:
    """Return the adapter registered for *name*, or the generic fallback."""
    return ADAPTERS.get(name, _GENERIC)
