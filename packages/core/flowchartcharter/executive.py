"""CEO / CFO / Board — executive layer; intervenes only on sync or hard halt."""
from __future__ import annotations
from typing import Dict, List, Optional
from .agents import Agent, BossAgent
from .vectors import (
    StrategyVector,
    BudgetVector,
    GovernanceVector,
    OpsVector,
    RhythmAudit,
)


class CEOAgent(Agent):
    def __init__(self, name: str = "CEO-Prime"):
        super().__init__(name, "Chief Executive Officer", {"strategy": 1.0, "general": 0.3})
        self.corporate_rank = 20.0
        self.talent_eligible = False

    def issue_strategy(
        self,
        charter_id: str,
        *,
        priority: float = 0.7,
        budget_cap_tokens: int = 50_000,
        quality_floor: float = 0.90,
        patches: Optional[List[str]] = None,
    ) -> StrategyVector:
        return StrategyVector(
            from_role="CEO",
            charter_id=charter_id,
            priority=priority,
            budget_cap_tokens=budget_cap_tokens,
            quality_floor=quality_floor,
            playbook_patches=tuple(patches or ()),
            escalate_to_board=False,
        )


class CFOAgent(Agent):
    def __init__(self, name: str = "CFO-Ledger"):
        super().__init__(name, "Chief Financial Officer", {"budget": 1.0, "general": 0.3})
        self.corporate_rank = 18.0
        self.talent_eligible = False

    def issue_budget(
        self,
        charter_id: str,
        *,
        token_spend: int,
        token_budget: int = 50_000,
        gamma: float = 0.001,
    ) -> BudgetVector:
        return BudgetVector(
            from_role="CFO",
            charter_id=charter_id,
            token_spend=token_spend,
            token_budget=token_budget,
            cost_penalty_gamma=gamma,
            halt_if_over=token_spend > token_budget,
        )


class BoardAgent(Agent):
    def __init__(self, name: str = "Board-Spectre"):
        super().__init__(name, "Executive Board", {"governance": 1.0, "general": 0.2})
        self.corporate_rank = 25.0
        self.talent_eligible = False

    def review_hand_off(
        self,
        charter_id: str,
        *,
        trust: bool,
        quality: float,
        quality_floor: float = 0.90,
        notes: str = "",
    ) -> GovernanceVector:
        approve = trust and quality >= quality_floor
        return GovernanceVector(
            from_role="Board",
            charter_id=charter_id,
            trust_signal=trust,
            approve_hand_off=approve,
            notes=notes or ("hand-off approved" if approve else "hand-off withheld"),
        )


class RhythmValidatorAgent(Agent):
    """Independent maker-checker at rhythm markers — never the implementor."""

    def __init__(self, name: str = "Validator-1"):
        super().__init__(name, "Rhythm Marker Validator", {"audit": 1.0, "general": 0.4})
        self.corporate_rank = 4.0
        self.talent_eligible = False

    def audit(
        self,
        charter_id: str,
        *,
        marker: str,
        quality: float,
        threshold: float = 0.90,
        remediation_loops: int = 0,
        schema_ok: bool = True,
    ) -> RhythmAudit:
        issues: List[str] = []
        if quality < threshold:
            issues.append(f"quality {quality:.3f} < {threshold}")
        if not schema_ok:
            issues.append("schema invalid")
        if remediation_loops > 3:
            issues.append("remediation cap exceeded")
        passed = len(issues) == 0
        return RhythmAudit(
            marker=marker,
            charter_id=charter_id,
            quality=quality,
            threshold=threshold,
            passed=passed,
            remediation_loops=remediation_loops,
            blocking_issues=tuple(issues),
        )


class ExecutiveBoard:
    """Idle-time executive layer; posts only typed vectors."""

    def __init__(self) -> None:
        self.ceo = CEOAgent()
        self.cfo = CFOAgent()
        self.board = BoardAgent()
        self.validator = RhythmValidatorAgent()

    def monday_guidance(
        self,
        charter_id: str,
        *,
        token_spend: int,
        token_budget: int,
        trust: bool,
        quality: float,
    ) -> List:
        strategy = self.ceo.issue_strategy(charter_id)
        budget = self.cfo.issue_budget(charter_id, token_spend=token_spend, token_budget=token_budget)
        gov = self.board.review_hand_off(charter_id, trust=trust, quality=quality)
        return [strategy, budget, gov]

    def gm_ops_vector(
        self,
        charter_id: str,
        outcomes: Dict[str, str],
        fitness_snapshot: Dict[str, float],
        playbook: List[str],
    ) -> OpsVector:
        return OpsVector(
            from_role="GM",
            charter_id=charter_id,
            roster_outcomes=dict(outcomes),
            fitness_snapshot=dict(fitness_snapshot),
            playbook_updates=tuple(playbook[:12]),
        )
