"""CharterHarness — the car under the Charter.

Charter owns the path. This kernel is how agents walk it without
wandering, crashing, or lying about being finished.

{charter_valid ∧ armed ∧ under_cfo}
    superstep()
{rhythm_emitted ∧ (effect xor blocked) ∧ notebook_committed}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .action_units import (
    ActionUnit,
    ActionUnit_GitHubPR,
    ActionUnit_SlackWebhook,
    create_action_unit,
)
from .durable_notebook import DurableNotebook, NotebookRecord
from .execution_sandbox import ExecutionSandbox, SandboxPolicy
from .retrieval_port import RetrievalPort, RetrievalResult


class KillState(str, Enum):
    ARMED = "ARMED"
    HALTED = "HALTED"


class KillSwitchError(RuntimeError):
    """Raised when a side-effect is attempted after HALT."""

    def __init__(self, reason: str = "halted") -> None:
        self.reason = reason
        super().__init__(f"KillSwitch HALT: {reason}")


@dataclass
class KillSwitch:
    """One stop button. HALT freezes new side-effects."""

    state: KillState = KillState.ARMED
    reason: str = ""
    halt_count: int = 0

    @property
    def armed(self) -> bool:
        return self.state is KillState.ARMED

    def halt(self, reason: str = "operator") -> None:
        self.state = KillState.HALTED
        self.reason = reason or "operator"
        self.halt_count += 1
        from .kill_law import write_halt

        write_halt(self.reason)

    def arm(self) -> None:
        self.state = KillState.ARMED
        self.reason = ""
        from .kill_law import clear_halt

        clear_halt()

    def assert_armed(self) -> None:
        if not self.armed:
            raise KillSwitchError(self.reason or "halted")


class ToolPort:
    """Uniform hands. Schema-first ActionUnits only. No raw shell."""

    def __init__(
        self,
        *,
        sandbox: Optional[ExecutionSandbox] = None,
        kill: Optional[KillSwitch] = None,
    ) -> None:
        self.sandbox = sandbox or ExecutionSandbox()
        self.kill = kill or KillSwitch()
        self._units: Dict[str, ActionUnit] = {
            "ActionUnit_SlackWebhook": ActionUnit_SlackWebhook(),
            "ActionUnit_GitHubPR": ActionUnit_GitHubPR(),
            "slack": ActionUnit_SlackWebhook(),
            "github_pr": ActionUnit_GitHubPR(),
        }

    def register(self, name: str, unit: ActionUnit) -> None:
        self._units[name] = unit

    def resolve(self, action_type: str) -> ActionUnit:
        if action_type in self._units:
            return self._units[action_type]
        built = create_action_unit(action_type)
        self._units[action_type] = built
        return built

    def execute(
        self,
        action_type: str,
        agent: Any,
        payload: Any,
        *,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        refuse = self.sandbox.allow(
            action_type, halted=not self.kill.armed
        )
        if refuse:
            self.sandbox.note_result(blocked=True)
            status = (
                "HALTED"
                if refuse == "kill_switch_halted"
                else "BLOCKED_SANDBOX"
            )
            return {
                "status": status,
                "errors": [refuse],
                "http": False,
                "ok": False,
                "sandbox": True,
                "kill_state": self.kill.state.value,
            }
        unit = self.resolve(action_type)
        cfg = dict(config or {})
        if self.sandbox.policy.dry_run or not self.sandbox.policy.network_allowed:
            cfg.setdefault("dry_run", True)
            if hasattr(unit, "dry_run"):
                unit.dry_run = True
        result = unit.execute_action(agent, payload, config=cfg)
        blocked = str(result.get("status") or "").startswith("BLOCKED")
        self.sandbox.note_result(blocked=blocked)
        result["sandbox"] = True
        result["kill_state"] = self.kill.state.value
        result["isolation_score"] = self.sandbox.isolation_score()
        return result


@dataclass
class HarnessKernel:
    """The car. Charter calls this. This never owns the map."""

    kill: KillSwitch = field(default_factory=KillSwitch)
    sandbox: ExecutionSandbox = field(default_factory=ExecutionSandbox)
    notebook: DurableNotebook = field(default_factory=DurableNotebook)
    retrieval: RetrievalPort = field(default_factory=RetrievalPort)
    tools: ToolPort = field(init=False)
    audits: List[Dict[str, Any]] = field(default_factory=list)
    persist: bool = False

    def __post_init__(self) -> None:
        self.tools = ToolPort(sandbox=self.sandbox, kill=self.kill)
        from .kill_law import bind

        bind(self.kill, self.sandbox, persist=self.persist)
        if self.persist:
            self.notebook.enable_persist()

    def halt(self, reason: str = "operator") -> None:
        self.kill.halt(reason)

    def arm(self) -> None:
        self.kill.arm()

    def retrieve(self, query: str, *, mode: str = "simple") -> RetrievalResult:
        return self.retrieval.retrieve(query, mode=mode)

    def run_action(
        self,
        action_type: str,
        agent: Any,
        payload: Any,
        *,
        unit_id: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result = self.tools.execute(
            action_type, agent, payload, config=config
        )
        rhythm = _rhythm_from_action(result, unit_id or action_type)
        self.audits.append(rhythm)
        rec = self.notebook.commit(
            unit_id=unit_id or action_type,
            status=str(result.get("status") or "unknown"),
            rhythm_audit=rhythm,
            payload={"status": result.get("status")},
        )
        result["rhythm_audit"] = rhythm
        result["notebook"] = rec.to_dict()
        return result

    def is_done(self, required: int = 1) -> bool:
        """Finished is a harness fact. Unearned self-grades do not count."""
        if not self.kill.armed:
            return False
        if len(self.audits) < required:
            return False
        chunk = self.audits[-required:]
        return all(
            bool(a.get("passed")) and bool(a.get("earned")) for a in chunk
        )

    def claim_done(self, model_says_done: bool, *, required: int = 1) -> Dict[str, Any]:
        done = self.is_done(required=required)
        if model_says_done and not done:
            return {
                "done": False,
                "rejected": True,
                "reason": "model_claimed_done_without_rhythm",
                "kill_state": self.kill.state.value,
            }
        return {
            "done": done,
            "rejected": False,
            "reason": "harness_done" if done else "incomplete",
            "kill_state": self.kill.state.value,
        }

    def audit(self, system: Any) -> Dict[str, Any]:
        """Live toolbox: halt / cite / episode / QFS. Not a self-grade."""
        from .system_audit import run_system_audit

        receipt = run_system_audit(system)
        self.notebook.commit(
            unit_id="system_audit",
            status="ok" if receipt.get("ok") else "fail",
            payload={
                "kind": "system_audit",
                "failed": list(receipt.get("failed") or []),
            },
        )
        return receipt

    def snapshot(self) -> Dict[str, Any]:
        last: Optional[NotebookRecord] = self.notebook.last()
        return {
            "kill_state": self.kill.state.value,
            "halt_reason": self.kill.reason,
            "isolation_score": self.sandbox.isolation_score(),
            "circuit_open": self.sandbox.circuit_open(),
            "notebook_records": len(self.notebook.records),
            "last_checkpoint": last.checkpoint_id if last else "",
            "audits": list(self.audits),
            "done": self.is_done(),
        }


def _rhythm_from_action(result: Dict[str, Any], unit_id: str) -> Dict[str, Any]:
    from .rhythm_gate import attach_rhythm, independent_audit

    existing = result.get("rhythm_audit")
    if (
        isinstance(existing, dict)
        and existing.get("type") == "RhythmAudit"
        and existing.get("earned") is True
    ):
        return existing
    audit = independent_audit(
        unit=type("U", (), {"id": unit_id, "unit_kind": "action"})(),
        result=result,
        charter_id=unit_id,
        implementor_role="Key Player",
        auditor_role="Audit Manager",
        marker="action",
    )
    return attach_rhythm(result, audit)["rhythm_audit"]
