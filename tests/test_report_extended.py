"""Extended tests for report.py: render_terminal with no findings (green border)."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from agentabi.compare import compare
from agentabi.models import Manifest
from agentabi.report import render_terminal


def _empty_manifest(runtime: str = "openclaw") -> Manifest:
    return Manifest(
        tool_version="0.1.0",
        runtime=runtime,
        runtime_confidence=1.0,
        root_label="test",
        components=[],
    )


def test_render_terminal_no_findings() -> None:
    report = compare(_empty_manifest(), _empty_manifest())
    assert report.findings == []
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    render_terminal(report, console, verbose=False)
    output = buf.getvalue()
    assert "100" in output
    assert "No findings" in output


def test_render_terminal_verbose_no_findings() -> None:
    report = compare(_empty_manifest(), _empty_manifest())
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    render_terminal(report, console, verbose=True)
    output = buf.getvalue()
    assert "Limitations" in output
