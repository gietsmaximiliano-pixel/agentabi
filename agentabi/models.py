"""Pydantic models for the normalized manifest and diff report."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MANIFEST_VERSION = "1"


class Severity(StrEnum):
    """Finding severity levels, from least to most severe."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    BREAKING = "breaking"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.HIGH: 2,
    Severity.BREAKING: 3,
}


class Category(StrEnum):
    """Normalized component categories."""

    CONTEXT = "context"
    MEMORY = "memory"
    SKILL = "skill"
    CRON = "cron"
    HOOK = "hook"
    TOOL_POLICY = "tool_policy"
    MCP = "mcp"
    CHANNEL = "channel"
    DELIVERY_TARGET = "delivery_target"
    RUNTIME_CONFIG = "runtime_config"
    SECRET_FILE = "secret_file"
    UNKNOWN = "unknown"


class StrictModel(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class Component(StrictModel):
    """A single normalized piece of persistent agent state."""

    id: str
    category: Category
    name: str
    path: str
    digest: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    warnings: list[str] = Field(default_factory=list)


class ScanStats(StrictModel):
    """Statistics and limitations recorded during a scan."""

    files_seen: int = 0
    files_hashed: int = 0
    secret_files_skipped: int = 0
    symlinks_skipped: int = 0
    unreadable_files: int = 0
    truncated: bool = False
    notes: list[str] = Field(default_factory=list)


class Manifest(StrictModel):
    """Versioned, normalized snapshot of an agent state directory."""

    manifest_version: str = MANIFEST_VERSION
    tool: str = "agentabi"
    tool_version: str
    runtime: str
    runtime_confidence: float
    root_label: str
    components: list[Component] = Field(default_factory=list)
    stats: ScanStats = Field(default_factory=ScanStats)


class Finding(StrictModel):
    """A detected operational regression or risk."""

    id: str
    severity: Severity
    category: Category
    title: str
    detail: str
    component_ids: list[str] = Field(default_factory=list)
    remediation: str | None = None


class ComponentChange(StrictModel):
    """Per-component comparison status between two manifests."""

    key: str
    category: Category
    name: str
    status: str
    before_path: str | None = None
    after_path: str | None = None


class DiffReport(StrictModel):
    """Full comparison report between a source and a candidate manifest."""

    report_version: str = "1"
    tool_version: str
    source_runtime: str
    target_runtime: str
    score: int
    recommendation: str
    findings: list[Finding] = Field(default_factory=list)
    changes: list[ComponentChange] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)
    privacy_note: str = (
        "AgentABI ran fully offline, never read secret files, and redacted "
        "sensitive keys before writing this report."
    )
