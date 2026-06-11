# AgentABI

> Detect what an AI-agent update or migration will forget, disable, or silently change before you deploy it.

AgentABI is a **local-first, read-only compatibility checker** for persistent AI-agent state. It compares an existing installation with a candidate updated or migrated state directory and detects operational regressions: lost memory, vanished skills, disappeared cron deliveries, broadened permissions, and more.

> AgentABI is an independent community project. It is not affiliated with OpenClaw, Hermes Agent, Nous Research, Anthropic, or OpenAI.

## Why

Agent updates and cross-runtime migrations routinely break things silently: a memory directory is not copied, a required skill is dropped, a cron job loses its delivery target, or a tool policy quietly becomes `allow: ["*"]`. AgentABI catches these regressions **before** you deploy.

## Guarantees

- **Offline.** No network requests, ever.
- **Deterministic.** Same inputs always produce the same manifests and reports.
- **Read-only.** Input directories are never modified.
- **Secret-safe.** Secret files (`.env`, `auth.json`, `*.pem`, `id_rsa`, ...) are never opened; only their existence and size are recorded. Sensitive metadata keys (`token`, `api_key`, `webhook`, ...) are recursively redacted.
- **Bounded.** Symlinks pointing outside the scanned root are never followed; recursion depth, file count, and file size are limited.

## Supported runtimes (v0.1.0)

- **OpenClaw**
- **Hermes Agent**
- **auto** (runtime auto-detection)

## Install

```bash
pip install agentabi          # once published
# or from source:
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Quickstart

```bash
# Try it instantly with synthetic data (no real state touched):
agentabi demo

# Snapshot an existing installation:
agentabi snapshot ~/agent-state --runtime auto --out before.json

# Snapshot the migrated candidate:
agentabi snapshot ~/agent-state-new --out after.json

# Compare:
agentabi diff before.json after.json --markdown report.md --fail-on breaking

# Or do it all in one step:
agentabi verify --source ~/agent-state --candidate ~/agent-state-new --out-dir ./report

# Health-check a single directory:
agentabi doctor ~/agent-state
```

## Commands

| Command | Purpose |
| --- | --- |
| `agentabi snapshot <path>` | Scan a state directory into a normalized, versioned JSON manifest. |
| `agentabi diff <before> <after>` | Compare two manifests; terminal, `--json`, and `--markdown` output; `--score-only`; `--fail-on none\|warning\|high\|breaking`. |
| `agentabi verify` | Snapshot `--source` and `--candidate`, compare, and write all reports to `--out-dir`. |
| `agentabi doctor <path>` | Inspect a single state directory and report runtime, components, and problems. |
| `agentabi demo` | Self-contained demo against synthetic states with injected regressions. |

Exit codes: `0` success / below threshold, `1` findings at or above `--fail-on`, `2` usage or input error.

## What gets normalized

Context and identity files, persistent memory, skills, cron jobs, hooks, tool policies, MCP declarations, channels, delivery targets, and runtime configuration. Every component records a stable id, category, logical name, relative source path, SHA-256 digest (when safe), redacted metadata, evidence, confidence, and warnings.

## Severities and scoring

- **BREAKING** (-20): missing persistent memory, all memory absent, enabled cron job or delivery target disappeared, required skill disappeared, duplicate destination skill names, privileged isolation explicitly weakened.
- **HIGH** (-10): substantial memory-count drop, tool-permission scope broadened, unrestricted shell introduced, MCP executable changed, active hook scope broadened, active channel disappeared, cron schedule materially changed.
- **WARNING** (-3): path relocation, skill digest changed, MCP argument changes, environment-variable requirement changes, unknown schema, incomplete scan, unsupported components.

The score starts at 100 and is clamped to 0-100. **Any breaking finding forces `Recommendation: DO NOT DEPLOY`.**

## Roadmap

- Claude Code runtime support (not supported in v0.1.0)
- More runtime adapters and community-contributed layouts
- Configurable severity policies

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security policy: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
