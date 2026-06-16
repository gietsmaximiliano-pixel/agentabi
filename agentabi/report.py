"""Report rendering: terminal, JSON, and Markdown."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentabi.models import SEVERITY_ORDER, DiffReport, Severity
from agentabi.scoring import DO_NOT_DEPLOY

SEVERITY_STYLES: dict[Severity, str] = {
    Severity.BREAKING: "bold red",
    Severity.HIGH: "red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}


def to_json(report: DiffReport) -> str:
    """Serialize a diff report as pretty JSON."""
    return report.to_pretty_json()


def to_markdown(report: DiffReport) -> str:
    """Render a diff report as a Markdown document."""
    lines = [
        "# AgentABI Compatibility Report",
        "",
        "## Executive Summary",
        "",
        f"- **Source runtime:** {report.source_runtime}",
        f"- **Target runtime:** {report.target_runtime}",
        f"- **Compatibility score:** {report.score}/100",
        f"- **Recommendation:** {report.recommendation}",
        f"- **Findings:** {len(report.findings)}",
        "",
        "## Findings",
        "",
    ]
    if not report.findings:
        lines += ["No findings. The candidate state preserves the source state.", ""]
    for severity in (Severity.BREAKING, Severity.HIGH, Severity.WARNING, Severity.INFO):
        group = [finding for finding in report.findings if finding.severity is severity]
        if not group:
            continue
        lines += [f"### {severity.value.upper()}", ""]
        for finding in group:
            lines.append(f"- **{finding.title}** - {finding.detail}")
            if finding.remediation:
                lines.append(f"  - Remediation: {finding.remediation}")
        lines.append("")
    lines += [
        "## Component Comparison",
        "",
        "| Component | Category | Status |",
        "| --- | --- | --- |",
    ]
    for change in report.changes:
        lines.append(f"| {change.name} | {change.category.value} | {change.status} |")
    lines += ["", "## Scan Limitations", ""]
    lines += [f"- {item}" for item in report.limitations]
    lines += ["", "## Manual-Review Checklist", ""]
    lines += [f"- [ ] {item}" for item in report.checklist]
    lines += ["", "## Privacy Note", "", report.privacy_note, ""]
    return "\n".join(lines)


def render_terminal(report: DiffReport, console: Console, *, verbose: bool = False) -> None:
    """Render a diff report to the terminal with Rich."""
    if report.recommendation == DO_NOT_DEPLOY:
        border = "red"
    elif report.findings:
        border = "yellow"
    else:
        border = "green"
    console.print(
        Panel(
            f"[bold]Score:[/bold] {report.score}/100\n"
            f"[bold]Recommendation:[/bold] {report.recommendation}",
            title="AgentABI Compatibility Report",
            border_style=border,
        )
    )
    console.print(f"Runtimes: {report.source_runtime} -> {report.target_runtime}")
    if report.findings:
        table = Table(title="Findings")
        table.add_column("Severity")
        table.add_column("Title")
        table.add_column("Detail")
        ordered = sorted(report.findings, key=lambda finding: -SEVERITY_ORDER[finding.severity])
        for finding in ordered:
            table.add_row(
                f"[{SEVERITY_STYLES[finding.severity]}]{finding.severity.value.upper()}[/]",
                finding.title,
                finding.detail,
            )
        console.print(table)
    else:
        console.print("[green]No findings.[/green]")
    if verbose:
        change_table = Table(title="Component Comparison")
        change_table.add_column("Component")
        change_table.add_column("Category")
        change_table.add_column("Status")
        for change in report.changes:
            change_table.add_row(change.name, change.category.value, change.status)
        console.print(change_table)
        console.print("Limitations:")
        for item in report.limitations:
            console.print(f"  - {item}")
    console.print(f"[dim]{report.privacy_note}[/dim]")
