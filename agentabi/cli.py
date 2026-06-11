"""AgentABI command-line interface."""

import json
import tempfile
from pathlib import Path

import typer
from rich.console import Console

from agentabi import __version__
from agentabi.compare import compare
from agentabi.demo import build_demo_states
from agentabi.models import SEVERITY_ORDER, DiffReport, Manifest, Severity
from agentabi.report import render_terminal, to_json, to_markdown
from agentabi.scanner import ScanError, snapshot as scan_snapshot

app = typer.Typer(
    name="agentabi",
    help="Detect what an AI-agent update or migration will forget, disable, or silently change.",
    no_args_is_help=True,
)
console = Console()

RUNTIME_CHOICES = ("auto", "openclaw", "hermes")
FAIL_ON_CHOICES = ("none", "warning", "high", "breaking")


def _check_choice(value: str, choices: tuple[str, ...], option: str) -> str:
    if value not in choices:
        console.print(
            f"[red]error:[/red] invalid value for {option}: {value!r} "
            f"(choose from {', '.join(choices)})"
        )
        raise typer.Exit(2)
    return value


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"agentabi {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """AgentABI: a local-first, read-only compatibility checker for AI-agent state."""


def _snapshot(path: Path, runtime: str) -> Manifest:
    try:
        return scan_snapshot(path, runtime)
    except ScanError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(2) from exc


def _load_manifest(path: Path) -> Manifest:
    try:
        return Manifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        console.print(f"[red]error:[/red] cannot load manifest {path}: {exc}")
        raise typer.Exit(2) from exc


def _exit_for(report: DiffReport, fail_on: str) -> None:
    if fail_on == "none":
        raise typer.Exit(0)
    threshold = SEVERITY_ORDER[Severity(fail_on)]
    if any(SEVERITY_ORDER[finding.severity] >= threshold for finding in report.findings):
        raise typer.Exit(1)
    raise typer.Exit(0)


@app.command()
def snapshot(
    path: Path = typer.Argument(..., help="Agent state directory to scan (read-only)."),
    runtime: str = typer.Option("auto", "--runtime", help="auto|openclaw|hermes"),
    out: Path | None = typer.Option(None, "--out", help="Write the manifest to this file."),
    json_output: bool = typer.Option(False, "--json", help="Print the manifest as JSON."),
    verbose: bool = typer.Option(False, "--verbose", help="List discovered components."),
) -> None:
    """Scan a state directory and produce a normalized manifest."""
    _check_choice(runtime, RUNTIME_CHOICES, "--runtime")
    manifest = _snapshot(path, runtime)
    payload = manifest.model_dump_json(indent=2) + "\n"
    if out:
        out.write_text(payload, encoding="utf-8")
        console.print(f"Manifest written to {out}")
    if json_output:
        typer.echo(payload, nl=False)
    elif not out:
        console.print(f"Runtime: {manifest.runtime} (confidence {manifest.runtime_confidence})")
        console.print(f"Components: {len(manifest.components)}")
        if verbose:
            for component in manifest.components:
                console.print(
                    f"  - [{component.category.value}] {component.name} ({component.path})"
                )


@app.command()
def diff(
    before: Path = typer.Argument(..., help="Manifest of the existing installation."),
    after: Path = typer.Argument(..., help="Manifest of the candidate state."),
    json_output: bool = typer.Option(False, "--json", help="Print the report as JSON."),
    markdown: Path | None = typer.Option(None, "--markdown", help="Write a Markdown report."),
    fail_on: str = typer.Option("breaking", "--fail-on", help="none|warning|high|breaking"),
    score_only: bool = typer.Option(False, "--score-only", help="Print only the score."),
    verbose: bool = typer.Option(False, "--verbose", help="Show the component comparison."),
) -> None:
    """Compare two manifests and report operational regressions."""
    _check_choice(fail_on, FAIL_ON_CHOICES, "--fail-on")
    report = compare(_load_manifest(before), _load_manifest(after))
    if markdown:
        markdown.write_text(to_markdown(report), encoding="utf-8")
    if score_only:
        typer.echo(str(report.score))
    elif json_output:
        typer.echo(to_json(report), nl=False)
    else:
        render_terminal(report, console, verbose=verbose)
    _exit_for(report, fail_on)


@app.command()
def verify(
    source: Path = typer.Option(..., "--source", help="Existing installation directory."),
    candidate: Path = typer.Option(..., "--candidate", help="Candidate state directory."),
    from_runtime: str = typer.Option("auto", "--from", help="auto|openclaw|hermes"),
    to_runtime: str = typer.Option("auto", "--to", help="auto|openclaw|hermes"),
    out_dir: Path | None = typer.Option(None, "--out-dir", help="Write manifests and reports."),
    json_output: bool = typer.Option(False, "--json", help="Print the report as JSON."),
    fail_on: str = typer.Option("breaking", "--fail-on", help="none|warning|high|breaking"),
) -> None:
    """Snapshot both states, compare them, and write reports."""
    _check_choice(from_runtime, RUNTIME_CHOICES, "--from")
    _check_choice(to_runtime, RUNTIME_CHOICES, "--to")
    _check_choice(fail_on, FAIL_ON_CHOICES, "--fail-on")
    before = _snapshot(source, from_runtime)
    after = _snapshot(candidate, to_runtime)
    report = compare(before, after)
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        source_payload = before.model_dump_json(indent=2) + "\n"
        candidate_payload = after.model_dump_json(indent=2) + "\n"
        (out_dir / "source.manifest.json").write_text(source_payload, encoding="utf-8")
        (out_dir / "candidate.manifest.json").write_text(candidate_payload, encoding="utf-8")
        (out_dir / "report.json").write_text(to_json(report), encoding="utf-8")
        (out_dir / "report.md").write_text(to_markdown(report), encoding="utf-8")
    if json_output:
        typer.echo(to_json(report), nl=False)
    else:
        render_terminal(report, console, verbose=False)
    _exit_for(report, fail_on)


@app.command()
def doctor(
    path: Path = typer.Argument(..., help="Agent state directory to inspect (read-only)."),
    runtime: str = typer.Option("auto", "--runtime", help="auto|openclaw|hermes"),
    json_output: bool = typer.Option(False, "--json", help="Print the summary as JSON."),
    verbose: bool = typer.Option(False, "--verbose", help="List discovered components."),
) -> None:
    """Inspect a single state directory and report its health."""
    _check_choice(runtime, RUNTIME_CHOICES, "--runtime")
    manifest = _snapshot(path, runtime)
    issues = sorted(
        {
            warning
            for component in manifest.components
            for warning in component.warnings
            if "secret file" not in warning
        }
    )
    if json_output:
        summary = {
            "runtime": manifest.runtime,
            "runtime_confidence": manifest.runtime_confidence,
            "components": len(manifest.components),
            "secret_files_skipped": manifest.stats.secret_files_skipped,
            "warnings": issues,
            "truncated": manifest.stats.truncated,
        }
        typer.echo(json.dumps(summary, indent=2))
        return
    console.print(f"Runtime: {manifest.runtime} (confidence {manifest.runtime_confidence})")
    console.print(f"Components discovered: {len(manifest.components)}")
    console.print(f"Secret files skipped (never read): {manifest.stats.secret_files_skipped}")
    for warning in issues:
        console.print(f"[yellow]warning:[/yellow] {warning}")
    if verbose:
        for component in manifest.components:
            console.print(f"  - [{component.category.value}] {component.name}")
    if not issues:
        console.print("[green]No problems detected.[/green]")


@app.command()
def demo() -> None:
    """Run a self-contained demo against synthetic state directories."""
    with tempfile.TemporaryDirectory(prefix="agentabi-demo-") as tmp:
        source, candidate = build_demo_states(Path(tmp))
        console.print(
            "[bold]AgentABI demo:[/bold] simulating an OpenClaw -> Hermes migration "
            "with injected regressions.\n"
        )
        report = compare(scan_snapshot(source, "auto"), scan_snapshot(candidate, "auto"))
        render_terminal(report, console, verbose=True)
    console.print("\nDemo complete. No real agent state was touched.")
