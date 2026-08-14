"""CEO / CFO / Board — executive layer; CFO applies budget matrix before collapse."""

from __future__ import annotations
from typing import Any, Dict, List, Mapping, Optional, Tuple
from .agents import Agent
from .quantum import DEFAULT_PATH_COSTS, PATH_LITE, apply_cfo_budget_matrix
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
    """Token Economics Override — hard interrupt before Measurement (Collapse)."""

    def __init__(self, name: str = "CFO-Ledger"):
        super().__init__(name, "Chief Financial Officer", {"budget": 1.0, "general": 0.3})
        self.corporate_rank = 18.0
        self.talent_eligible = False
        self.path_costs: Dict[str, float] = dict(DEFAULT_PATH_COSTS)
        self.reserve_margin: float = 500.0  # keep headroom tokens

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

    def budget_constraint_matrix(
        self,
        *,
        token_spend: int,
        token_budget: int,
        path_weights: Mapping[str, float],
        path_costs: Optional[Mapping[str, float]] = None,
    ) -> Dict[str, object]:
        """Apply CFO matrix before wave-function collapse.

        Returns adjusted weights, blocked paths, and whether lite was forced.
        """
        remaining = float(token_budget - token_spend)
        costs = dict(path_costs or self.path_costs)
        adjusted, blocked, forced = apply_cfo_budget_matrix(
            dict(path_weights),
            costs,
            remaining_budget=remaining,
            margin=self.reserve_margin,
            force_lite_path=PATH_LITE,
        )
        return {
            "type": "CFOBudgetMatrix",
            "from": "CFO",
            "remaining_budget": remaining,
            "reserve_margin": self.reserve_margin,
            "path_costs": costs,
            "adjusted_weights": adjusted,
            "blocked_paths": blocked,
            "force_lite": forced,
            "interrupt": bool(blocked or forced),
        }

    def pre_collapse_gate(
        self,
        *,
        token_spend: int,
        token_budget: int,
        muscle_memory: Mapping[str, float],
    ) -> Tuple[Dict[str, float], Dict[str, object]]:
        """Convenience: return (weights_for_superposition, matrix_report)."""
        report = self.budget_constraint_matrix(
            token_spend=token_spend,
            token_budget=token_budget,
            path_weights=muscle_memory,
        )
        weights = dict(report["adjusted_weights"])  # type: ignore[arg-type]
        return weights, report


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
        qs: Optional[float] = None,
        result: Optional[Dict[str, Any]] = None,
        implementor_role: str = "Key Player",
    ) -> RhythmAudit:
        """Grade evidence. Handed ``quality`` is claimed and ignored."""
        from .rhythm_gate import collect_evidence, independent_audit

        if result is not None:
            ev = collect_evidence(
                result,
                implementor_role=implementor_role,
                auditor_role="Audit Manager",
            )
        else:
            ev = collect_evidence(
                {
                    "ok": bool(schema_ok),
                    "blocked": not bool(schema_ok),
                    "gate": {"valid": bool(schema_ok), "quality": quality},
                    "quality": quality,
                    "dry_run": True,
                },
                implementor_role=implementor_role,
                auditor_role="Audit Manager",
            )
        return independent_audit(
            evidence=ev,
            charter_id=charter_id,
            threshold=threshold,
            remediation_loops=remediation_loops,
            implementor_role=implementor_role,
            auditor_role="Audit Manager",
            marker=marker,
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
        budget = self.cfo.issue_budget(
            charter_id, token_spend=token_spend, token_budget=token_budget
        )
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
