"""Strict JSON performance vectors — executive wire format (no free-form NL)."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional, Union
import json


@dataclass(frozen=True)
class StrategyVector:
    type: Literal["StrategyVector"] = "StrategyVector"
    from_role: str = "CEO"
    charter_id: str = ""
    priority: float = 0.5
    budget_cap_tokens: int = 50_000
    quality_floor: float = 0.90
    playbook_patches: tuple[str, ...] = ()
    escalate_to_board: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["from"] = d.pop("from_role")
        d["playbook_patches"] = list(self.playbook_patches)
        return d


@dataclass(frozen=True)
class BudgetVector:
    type: Literal["BudgetVector"] = "BudgetVector"
    from_role: str = "CFO"
    charter_id: str = ""
    token_spend: int = 0
    token_budget: int = 50_000
    cost_penalty_gamma: float = 0.001
    halt_if_over: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["from"] = d.pop("from_role")
        return d


@dataclass(frozen=True)
class GovernanceVector:
    type: Literal["GovernanceVector"] = "GovernanceVector"
    from_role: str = "Board"
    charter_id: str = ""
    trust_signal: bool = False
    approve_hand_off: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if len(self.notes) > 120:
            object.__setattr__(self, "notes", self.notes[:120])

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["from"] = d.pop("from_role")
        return d


@dataclass(frozen=True)
class OpsVector:
    type: Literal["OpsVector"] = "OpsVector"
    from_role: str = "GM"
    charter_id: str = ""
    roster_outcomes: Dict[str, str] = field(default_factory=dict)
    fitness_snapshot: Dict[str, float] = field(default_factory=dict)
    playbook_updates: tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["from"] = d.pop("from_role")
        d["playbook_updates"] = list(self.playbook_updates)
        return d


@dataclass(frozen=True)
class RhythmAudit:
    type: Literal["RhythmAudit"] = "RhythmAudit"
    marker: str = "gate"
    charter_id: str = ""
    quality: float = 0.0
    threshold: float = 0.90
    passed: bool = False
    remediation_loops: int = 0
    blocking_issues: tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["blocking_issues"] = list(self.blocking_issues)
        return d


ExecutiveVector = Union[StrategyVector, BudgetVector, GovernanceVector, OpsVector, RhythmAudit]

ALLOWED_EXEC_TYPES = frozenset(
    {"StrategyVector", "BudgetVector", "GovernanceVector", "OpsVector", "RhythmAudit"}
)


def validate_executive_payload(payload: Dict[str, Any]) -> bool:
    """Reject free-form NL; only strict vector types allowed on the executive wire."""
    t = payload.get("type")
    if t not in ALLOWED_EXEC_TYPES:
        return False
    if t == "StrategyVector":
        return "charter_id" in payload and "budget_cap_tokens" in payload
    if t == "BudgetVector":
        return "token_spend" in payload and "token_budget" in payload
    if t == "GovernanceVector":
        return "trust_signal" in payload and "approve_hand_off" in payload
    if t == "OpsVector":
        return "roster_outcomes" in payload
    if t == "RhythmAudit":
        return "marker" in payload and "quality" in payload and "passed" in payload
    return False


def vector_json(vec: ExecutiveVector) -> str:
    return json.dumps(vec.to_dict(), separators=(",", ":"), sort_keys=True)
