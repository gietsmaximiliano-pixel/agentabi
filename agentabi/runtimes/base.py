"""Runtime adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from agentabi.models import Component


class RuntimeAdapter(ABC):
    """Normalizes one agent runtime's on-disk layout into components."""

    name: str = "unknown"

    @abstractmethod
    def detect(self, root: Path) -> float:
        """Return a detection confidence for *root* between 0.0 and 1.0."""

    @abstractmethod
    def scan(self, root: Path, files: list[Path]) -> list[Component]:
        """Produce normalized components for *root* given pre-walked *files*."""
