"""Diff engine: compare two normalized manifests and emit findings."""

from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from agentabi import __version__
from agentabi.models import (
    SEVERITY_ORDER,
    Category,
    Component,
    ComponentChange,
    DiffReport,
    Finding,
    Manifest,
    Severity,
)
from agentabi.scoring import recommend, score

ComponentMap = dict[tuple[str, str], Component]

CHECKLIST = [
    "Confirm persistent memory files are present and readable in the candidate state.",
    "Re-run each enabled cron job manually once and confirm delivery arrives.",
    "Exercise every required skill with a dry-run prompt.",
    "Review tool and shell permissions against your least-privilege baseline.",
    "Verify MCP servers start with the expected executable and arguments.",
    "Send a test message through every active channel.",
]

BASE_LIMITATIONS = [
    "Static analysis only: candidate behavior is never executed or simulated.",
    "Secret files are never opened, so their contents cannot be compared.",
    "Cross-runtime path and digest changes are reported conservatively.",
]


def _index(manifest: Manifest) -> ComponentMap:
    indexed: ComponentMap = {}
    for component in manifest.components:
        indexed.setdefault((component.category.value, component.name), component)
    return indexed


def compare(before: Manifest, after: Manifest) -> DiffReport:
    """Compare *before* (source) with *after* (candidate) and build a report."""
    before_map = _index(before)
    after_map = _index(after)
    same_runtime = before.runtime == after.runtime

    findings: list[Finding] = []
    findings += _memory_findings(before_map, after_map)
    findings += _removal_findings(before_map, after_map)
    findings += _duplicate_skill_findings(after)
    findings += _tool_policy_findings(before_map, after_map)
    findings += _changed_findings(before_map, after_map, same_runtime)
    findings += _schema_findings(after)
    findings += _scan_findings(before, after)
    findings.sort(key=lambda finding: (-SEVERITY_ORDER[finding.severity], finding.id))

    limitations = list(BASE_LIMITATIONS)
    limitations += [f"source scan: {note}" for note in before.stats.notes]
    limitations += [f"candidate scan: {note}" for note in after.stats.notes]

    return DiffReport(
        tool_version=__version__,
        source_runtime=before.runtime,
        target_runtime=after.runtime,
        score=score(findings),
        recommendation=recommend(findings),
        findings=findings,
        changes=_changes(before_map, after_map),
        limitations=limitations,
        checklist=list(CHECKLIST),
    )


def _memory_findings(before_map: ComponentMap, after_map: ComponentMap) -> list[Finding]:
    findings: list[Finding] = []
    before_memory = sorted(name for cat, name in before_map if cat == Category.MEMORY.value)
    after_memory = sorted(name for cat, name in after_map if cat == Category.MEMORY.value)
    if before_memory and not after_memory:
        findings.append(
            Finding(
                id="memory-all-missing",
                severity=Severity.BREAKING,
                category=Category.MEMORY,
                title="All persistent memory is unexpectedly absent",
                detail=(
                    f"The source state contains {len(before_memory)} memory file(s); "
                    "the candidate contains none."
                ),
                remediation="Copy the persistent memory store into the candidate state "
                "before deploying.",
            )
        )
        return findings
    missing = [name for name in before_memory if (Category.MEMORY.value, name) not in after_map]
    for name in missing:
        findings.append(
            Finding(
                id=f"memory-missing:{name}",
                severity=Severity.BREAKING,
                category=Category.MEMORY,
                title=f"Persistent memory '{name}' is missing after migration",
                detail="A memory file present in the source state has no counterpart "
                "in the candidate.",
                component_ids=[before_map[(Category.MEMORY.value, name)].id],
            )
        )
    if before_memory and after_memory and len(after_memory) <= len(before_memory) // 2:
        findings.append(
            Finding(
                id="memory-count-drop",
                severity=Severity.HIGH,
                category=Category.MEMORY,
                title="Substantial memory-count drop",
                detail=(f"Memory files dropped from {len(before_memory)} to {len(after_memory)}."),
            )
        )
    return findings


def _removal_findings(before_map: ComponentMap, after_map: ComponentMap) -> list[Finding]:
    findings: list[Finding] = []
    for key in sorted(before_map):
        if key in after_map:
            continue
        category_value, name = key
        component = before_map[key]
        if category_value == Category.CRON.value and component.metadata.get("enabled", True):
            findings.append(
                Finding(
                    id=f"cron-missing:{name}",
                    severity=Severity.BREAKING,
                    category=Category.CRON,
                    title=f"Enabled cron job '{name}' disappeared",
                    detail="An enabled scheduled job in the source state is absent from "
                    "the candidate.",
                    component_ids=[component.id],
                )
            )
        elif category_value == Category.DELIVERY_TARGET.value:
            findings.append(
                Finding(
                    id=f"delivery-missing:{name}",
                    severity=Severity.BREAKING,
                    category=Category.DELIVERY_TARGET,
                    title=f"Cron delivery target '{name}' disappeared",
                    detail="A scheduled job lost its delivery target; results would be "
                    "produced but never delivered.",
                    component_ids=[component.id],
                )
            )
        elif category_value == Category.SKILL.value:
            if component.metadata.get("required"):
                findings.append(
                    Finding(
                        id=f"skill-missing:{name}",
                        severity=Severity.BREAKING,
                        category=Category.SKILL,
                        title=f"Required skill '{name}' disappeared",
                        detail="A skill the source configuration marks as required is "
                        "absent from the candidate.",
                        component_ids=[component.id],
                    )
                )
            else:
                findings.append(
                    Finding(
                        id=f"skill-absent:{name}",
                        severity=Severity.WARNING,
                        category=Category.SKILL,
                        title=f"Skill '{name}' is absent from the candidate",
                        detail="A non-required skill present in the source state was not "
                        "found in the candidate.",
                        component_ids=[component.id],
                    )
                )
        elif category_value == Category.CHANNEL.value and component.metadata.get("enabled", True):
            findings.append(
                Finding(
                    id=f"channel-missing:{name}",
                    severity=Severity.HIGH,
                    category=Category.CHANNEL,
                    title=f"Active channel '{name}' disappeared",
                    detail="An enabled communication channel in the source state is absent "
                    "from the candidate.",
                    component_ids=[component.id],
                )
            )
    return findings


def _duplicate_skill_findings(after: Manifest) -> list[Finding]:
    counts = Counter(
        component.name for component in after.components if component.category is Category.SKILL
    )
    return [
        Finding(
            id=f"skill-duplicate:{name}",
            severity=Severity.BREAKING,
            category=Category.SKILL,
            title=f"Duplicate destination skill name '{name}'",
            detail=f"The candidate state defines the skill '{name}' {count} times; "
            "resolution is ambiguous.",
        )
        for name, count in sorted(counts.items())
        if count > 1
    ]


def _tool_policy_findings(before_map: ComponentMap, after_map: ComponentMap) -> list[Finding]:
    key = (Category.TOOL_POLICY.value, "tools")
    before_policy = before_map.get(key)
    after_policy = after_map.get(key)
    if before_policy is None or after_policy is None:
        return []
    findings: list[Finding] = []
    before_meta, after_meta = before_policy.metadata, after_policy.metadata
    if (
        before_meta.get("privileged_isolation") is True
        and after_meta.get("privileged_isolation") is False
    ):
        findings.append(
            Finding(
                id="isolation-weakened",
                severity=Severity.BREAKING,
                category=Category.TOOL_POLICY,
                title="Privileged workflow isolation explicitly weakened",
                detail="The candidate disables privileged_isolation that the source state "
                "enforces.",
            )
        )
    before_allow = {str(item) for item in before_meta.get("allow") or []}
    after_allow = {str(item) for item in after_meta.get("allow") or []}
    broadened = sorted(after_allow - before_allow)
    wildcard_added = "*" in after_allow and "*" not in before_allow
    if wildcard_added or (broadened and after_allow >= before_allow):
        findings.append(
            Finding(
                id="tools-broadened",
                severity=Severity.HIGH,
                category=Category.TOOL_POLICY,
                title="Tool-permission scope broadened",
                detail=f"New allowances in the candidate: {', '.join(broadened) or '*'}.",
            )
        )
    before_shell = str(before_meta.get("shell") or "").lower()
    after_shell = str(after_meta.get("shell") or "").lower()
    if after_shell == "unrestricted" and before_shell != "unrestricted":
        findings.append(
            Finding(
                id="shell-unrestricted",
                severity=Severity.HIGH,
                category=Category.TOOL_POLICY,
                title="Unrestricted shell access introduced",
                detail=f"Shell policy changed from '{before_shell or 'unset'}' to 'unrestricted'.",
            )
        )
    return findings


def _changed_findings(
    before_map: ComponentMap, after_map: ComponentMap, same_runtime: bool
) -> list[Finding]:
    findings: list[Finding] = []
    for key in sorted(set(before_map) & set(after_map)):
        category_value, name = key
        before_component = before_map[key]
        after_component = after_map[key]
        if category_value == Category.CRON.value:
            if before_component.metadata.get("schedule") != after_component.metadata.get(
                "schedule"
            ):
                findings.append(
                    Finding(
                        id=f"cron-schedule:{name}",
                        severity=Severity.HIGH,
                        category=Category.CRON,
                        title=f"Cron schedule for '{name}' materially changed",
                        detail=(
                            f"Schedule changed from "
                            f"'{before_component.metadata.get('schedule')}' to "
                            f"'{after_component.metadata.get('schedule')}'."
                        ),
                        component_ids=[before_component.id, after_component.id],
                    )
                )
        elif category_value == Category.MCP.value:
            if before_component.metadata.get("command") != after_component.metadata.get("command"):
                findings.append(
                    Finding(
                        id=f"mcp-command:{name}",
                        severity=Severity.HIGH,
                        category=Category.MCP,
                        title=f"MCP server '{name}' executable changed",
                        detail=(
                            f"Command changed from "
                            f"'{before_component.metadata.get('command')}' to "
                            f"'{after_component.metadata.get('command')}'."
                        ),
                        component_ids=[before_component.id, after_component.id],
                    )
                )
            elif before_component.metadata.get("args") != after_component.metadata.get("args"):
                findings.append(
                    Finding(
                        id=f"mcp-args:{name}",
                        severity=Severity.WARNING,
                        category=Category.MCP,
                        title=f"MCP server '{name}' argument structure changed",
                        detail="The launch arguments differ between source and candidate.",
                    )
                )
            if before_component.metadata.get("env_keys") != after_component.metadata.get(
                "env_keys"
            ):
                findings.append(
                    Finding(
                        id=f"mcp-env:{name}",
                        severity=Severity.WARNING,
                        category=Category.MCP,
                        title=f"Environment-variable requirements for '{name}' changed",
                        detail="The set of required environment variable names differs.",
                    )
                )
        elif category_value == Category.HOOK.value and after_component.metadata.get(
            "enabled", True
        ):
            before_events = set(before_component.metadata.get("events") or [])
            after_events = set(after_component.metadata.get("events") or [])
            if after_events > before_events:
                findings.append(
                    Finding(
                        id=f"hook-broadened:{name}",
                        severity=Severity.HIGH,
                        category=Category.HOOK,
                        title=f"Active hook '{name}' scope broadened",
                        detail="New events handled: "
                        f"{', '.join(sorted(after_events - before_events))}.",
                    )
                )
        elif category_value == Category.SKILL.value:
            if (
                before_component.digest
                and after_component.digest
                and before_component.digest != after_component.digest
                and PurePosixPath(before_component.path).suffix
                == PurePosixPath(after_component.path).suffix
            ):
                findings.append(
                    Finding(
                        id=f"skill-digest:{name}",
                        severity=Severity.WARNING,
                        category=Category.SKILL,
                        title=f"Skill '{name}' digest changed",
                        detail="The skill definition content changed; review the diff manually.",
                    )
                )
        if (
            same_runtime
            and before_component.path != after_component.path
            and category_value != Category.SECRET_FILE.value
        ):
            findings.append(
                Finding(
                    id=f"relocated:{category_value}:{name}",
                    severity=Severity.WARNING,
                    category=Category(category_value),
                    title=f"Unfamiliar path relocation for '{name}'",
                    detail=f"Path changed from '{before_component.path}' to "
                    f"'{after_component.path}' within the same runtime.",
                )
            )
    return findings


def _schema_findings(after: Manifest) -> list[Finding]:
    findings: list[Finding] = []
    malformed = sorted(
        {
            component.path
            for component in after.components
            for warning in component.warnings
            if "unknown schema" in warning or "unreadable" in warning
        }
    )
    if malformed:
        findings.append(
            Finding(
                id="schema-unknown",
                severity=Severity.WARNING,
                category=Category.RUNTIME_CONFIG,
                title="Unknown or malformed configuration schema",
                detail="Could not fully parse: " + ", ".join(malformed) + ".",
            )
        )
    unsupported = sorted(
        {component.name for component in after.components if component.category is Category.UNKNOWN}
    )
    if unsupported:
        findings.append(
            Finding(
                id="unsupported-components",
                severity=Severity.WARNING,
                category=Category.UNKNOWN,
                title="Unsupported components present",
                detail=f"{len(unsupported)} file(s) could not be classified by a supported "
                "runtime adapter.",
            )
        )
    return findings


def _scan_findings(before: Manifest, after: Manifest) -> list[Finding]:
    findings: list[Finding] = []
    for label, manifest in (("source", before), ("candidate", after)):
        if manifest.stats.truncated:
            findings.append(
                Finding(
                    id=f"scan-incomplete:{label}",
                    severity=Severity.WARNING,
                    category=Category.UNKNOWN,
                    title=f"Incomplete scan of the {label} state",
                    detail="Scan limits were reached; some components may be missing from "
                    "this report.",
                )
            )
    return findings


def _changes(before_map: ComponentMap, after_map: ComponentMap) -> list[ComponentChange]:
    changes: list[ComponentChange] = []
    for key in sorted(set(before_map) | set(after_map)):
        category_value, name = key
        before_component = before_map.get(key)
        after_component = after_map.get(key)
        if before_component is None:
            status = "added"
        elif after_component is None:
            status = "removed"
        elif (
            before_component.digest != after_component.digest
            or before_component.path != after_component.path
            or before_component.metadata != after_component.metadata
        ):
            status = "changed"
        else:
            status = "unchanged"
        changes.append(
            ComponentChange(
                key=f"{category_value}:{name}",
                category=Category(category_value),
                name=name,
                status=status,
                before_path=before_component.path if before_component else None,
                after_path=after_component.path if after_component else None,
            )
        )
    return changes
