"""Self-contained synthetic demo states.

Everything written here is fully synthetic. The demo never touches real agent
state, never reads secrets, and never performs network requests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OPENCLAW_CONFIG: dict[str, Any] = {
    "agent": {"name": "atlas"},
    "model": "synthetic-small",
    "required_skills": ["research", "reporter"],
    "tools": {
        "allow": ["browser", "files"],
        "shell": "sandboxed",
        "privileged_isolation": True,
    },
    "mcp": {
        "servers": {
            "search": {
                "command": "npx",
                "args": ["-y", "synthetic-search"],
                "env": {"SEARCH_API_KEY": "placeholder"},
            }
        }
    },
    "channels": {
        "telegram": {"enabled": True, "kind": "chat"},
        "email": {"enabled": True, "kind": "mail"},
    },
}

OPENCLAW_JOBS: list[dict[str, Any]] = [
    {
        "name": "daily-report",
        "schedule": "0 9 * * *",
        "enabled": True,
        "delivery": {"channel": "telegram"},
    },
    {
        "name": "weekly-digest",
        "schedule": "0 8 * * 1",
        "enabled": True,
        "delivery": {"channel": "email"},
    },
]

OPENCLAW_HOOKS: list[dict[str, Any]] = [
    {"name": "on-message", "events": ["message.received"], "scope": "inbound", "enabled": True}
]

HERMES_CONFIG = """\
identity:
  name: atlas
model: synthetic-small
required_skills:
  - research
  - reporter
tools:
  allow:
    - browser
    - files
  shell: sandboxed
  privileged_isolation: true
mcp:
  servers:
    search:
      command: bunx
      args:
        - -y
        - synthetic-search
      env:
        SEARCH_API_KEY: placeholder
channels:
  email:
    enabled: true
    kind: mail
"""

HERMES_SCHEDULES = """\
jobs:
  - name: daily-report
    schedule: "0 9 * * *"
    enabled: true
  - name: weekly-digest
    schedule: "0 8 * * 1"
    enabled: true
    deliver_to:
      channel: email
"""

HERMES_HOOKS = """\
hooks:
  - name: on-message
    events:
      - message.received
    scope: inbound
    enabled: true
"""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_demo_states(base: Path) -> tuple[Path, Path]:
    """Create a synthetic source/candidate pair with injected regressions."""
    source = base / "openclaw-source"
    candidate = base / "hermes-candidate"

    _write(source / "openclaw.json", json.dumps(OPENCLAW_CONFIG, indent=2) + "\n")
    _write(source / "AGENT.md", "# Atlas\n\nSynthetic identity context.\n")
    _write(source / "memory" / "core.md", "Core synthetic memory.\n")
    _write(source / "memory" / "2025-01.md", "January synthetic memory.\n")
    _write(source / "memory" / "2025-02.md", "February synthetic memory.\n")
    _write(source / "skills" / "research.md", "# research\n\nSynthetic skill.\n")
    _write(source / "skills" / "reporter.md", "# reporter\n\nSynthetic skill.\n")
    _write(source / "cron" / "jobs.json", json.dumps(OPENCLAW_JOBS, indent=2) + "\n")
    _write(source / "hooks" / "hooks.json", json.dumps(OPENCLAW_HOOKS, indent=2) + "\n")

    _write(candidate / "hermes.yaml", HERMES_CONFIG)
    _write(candidate / "identity" / "AGENT.md", "# Atlas\n\nSynthetic identity context.\n")
    _write(candidate / "state" / "memory" / "core.md", "Core synthetic memory.\n")
    _write(candidate / "state" / "memory" / "2025-01.md", "January synthetic memory.\n")
    # memory/2025-02.md is intentionally lost in the migration.
    _write(
        candidate / "skills" / "research.yaml",
        "name: research\ndescription: Synthetic skill.\n",
    )
    # The reporter skill is intentionally lost in the migration.
    _write(candidate / "schedules.yaml", HERMES_SCHEDULES)
    _write(candidate / "hooks.yaml", HERMES_HOOKS)
    return source, candidate
