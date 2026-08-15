"""ExecutionSandbox — the playpen.

Not a slot engine. Isolates side-effects so agents cannot break the house.
Network is off unless allowlisted AND KillSwitch is ARMED AND schema passed.
No raw shell. Dry-run is the default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional


ALLOWED_ACTIONS: FrozenSet[str] = frozenset(
    {
        "ActionUnit_SlackWebhook",
        "ActionUnit_GitHubPR",
        "ActionUnit_WorldMouth",
        "slack",
        "github_pr",
        "world_mouth",
        "ask",
    }
)
DENIED_ACTIONS: FrozenSet[str] = frozenset(
    {
        "shell",
        "bash",
        "eval",
        "exec",
        "file_write",
        "os_system",
        "subprocess",
    }
)


class SandboxPolicyError(RuntimeError):
    """Playpen refused the call."""


@dataclass
class SandboxPolicy:
    dry_run: bool = True
    network_allowed: bool = False
    allow_shell: bool = False
    allowlist: FrozenSet[str] = ALLOWED_ACTIONS
    max_consecutive_blocks: int = 3


@dataclass
class ExecutionSandbox:
    """In-process isolation wrapper around ActionUnits."""

    policy: SandboxPolicy = field(default_factory=SandboxPolicy)
    consecutive_blocks: int = 0
    trips: int = 0

    def circuit_open(self) -> bool:
        return self.consecutive_blocks >= int(self.policy.max_consecutive_blocks)

    def allow(self, action_type: str, *, halted: bool) -> Optional[str]:
        if halted:
            return "kill_switch_halted"
        if self.policy.allow_shell:
            return "raw_shell_forbidden"
        kind = (action_type or "").strip()
        low = kind.lower()
        if kind in DENIED_ACTIONS or any(bit in low for bit in DENIED_ACTIONS):
            return "action_denied_by_default"
        if kind not in self.policy.allowlist and kind not in ALLOWED_ACTIONS:
            return "action_not_allowlisted"
        if self.circuit_open():
            self.trips += 1
            return "circuit_breaker_open"
        return None

    def note_result(self, blocked: bool) -> None:
        if blocked:
            self.consecutive_blocks += 1
        else:
            self.consecutive_blocks = 0

    def isolation_score(self) -> float:
        """1.0 = fully isolated playpen; drops if network or shell requested."""
        score = 1.0
        if self.policy.network_allowed:
            score -= 0.35
        if not self.policy.dry_run:
            score -= 0.25
        if self.policy.allow_shell:
            score = 0.0
        if self.circuit_open():
            score = min(score, 0.4)
        return max(0.0, round(score, 4))

    def policy_not_kernel(self) -> bool:
        """Honest: this is a policy playpen, not gVisor."""
        return True
