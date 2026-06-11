# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-11

### Added

- `agentabi snapshot`: normalize an agent state directory into a versioned JSON manifest.
- `agentabi diff`: compare two manifests with terminal, JSON, and Markdown reports,
  `--score-only`, and `--fail-on` exit-code thresholds.
- `agentabi verify`: one-step snapshot + compare + report bundle.
- `agentabi doctor`: single-directory health check.
- `agentabi demo`: self-contained synthetic demo.
- Runtime adapters for OpenClaw and Hermes Agent, plus auto-detection.
- Secret-file skipping, recursive metadata redaction, symlink-escape prevention,
  and scan limits (depth, file count, file size).
- Compatibility scoring (breaking -20, high -10, warning -3) with a forced
  `DO NOT DEPLOY` recommendation on any breaking finding.
- Fully synthetic fixtures and a comprehensive unit/integration test suite.

### Roadmap

- Claude Code runtime support (not included in 0.1.0).
