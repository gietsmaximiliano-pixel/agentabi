"""Compatibility scoring and deployment recommendation."""

from __future__ import annotations

from agentabi.models import Finding, Severity

PENALTIES: dict[Severity, int] = {
    Severity.BREAKING: 20,
    Severity.HIGH: 10,
    Severity.WARNING: 3,
    Severity.INFO: 0,
}

DO_NOT_DEPLOY = "DO NOT DEPLOY"


def score(findings: list[Finding]) -> int:
    """Return a 0-100 compatibility score for *findings*."""
    total = 100 - sum(PENALTIES[finding.severity] for finding in findings)
    return max(0, min(100, total))


def recommend(findings: list[Finding]) -> str:
    """Return a deployment recommendation. Any breaking finding forces DO NOT DEPLOY."""
    severities = {finding.severity for finding in findings}
    if Severity.BREAKING in severities:
        return DO_NOT_DEPLOY
    if Severity.HIGH in severities:
        return "REVIEW REQUIRED BEFORE DEPLOY"
    if Severity.WARNING in severities:
        return "DEPLOY WITH CAUTION"
    return "SAFE TO DEPLOY"
