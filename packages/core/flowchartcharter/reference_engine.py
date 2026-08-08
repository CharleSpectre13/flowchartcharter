"""FlowChartCharter reference engine — canonical blueprint simulation.

Audit patches V1–V3:
  V1 Delta-token bloat penalty
  V2 Bounded exponential speed score
  V3 Elastic / phantom handled at system layer (see elastic.py)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .fitness import (
    DEFAULT_EXPECTED_LATENCY_MS,
    reference_node_fitness,
    risk_from_fitness,
)


@dataclass
class TypedFlowUnit:
    """Playbook unit selected by wave-function collapse."""

    id: str
    description: str
    historical_success_rate: float
    avg_token_cost: int
    expected_input_schema: List[str] = field(default_factory=list)
    expected_output_schema: List[str] = field(default_factory=list)
    handles_uncertainty: float = 0.5
    expected_latency_ms: float = DEFAULT_EXPECTED_LATENCY_MS

    def __post_init__(self) -> None:
        if not 0.0 <= self.historical_success_rate <= 1.0:
            raise ValueError("historical_success_rate must be in [0, 1]")
        if self.avg_token_cost < 0:
            raise ValueError("avg_token_cost must be non-negative")
        self.handles_uncertainty = max(
            0.0, min(1.0, float(self.handles_uncertainty))
        )


@dataclass
class AgentFitness:
    """Telemetry for patched F(x) — tracks expected vs actual."""

    q_success: int = 1
    q_total: int = 1
    actual_latency_ms: float = 100.0
    actual_tokens_used: int = 500
    expected_tokens: int = 500
    expected_latency_ms: float = DEFAULT_EXPECTED_LATENCY_MS
    entanglement_errors: int = 0
    delta_t_ms: float = 100.0
    total_tokens: int = 500

    def __post_init__(self) -> None:
        if self.q_success < 0 or self.q_total < 0:
            raise ValueError("q_success/q_total must be non-negative")
        # sync aliases if caller set only legacy fields
        if self.delta_t_ms != 100.0 and self.actual_latency_ms == 100.0:
            self.actual_latency_ms = self.delta_t_ms
        if self.total_tokens != 500 and self.actual_tokens_used == 500:
            self.actual_tokens_used = self.total_tokens
        self.delta_t_ms = self.actual_latency_ms
        self.total_tokens = self.actual_tokens_used
        if self.actual_latency_ms < 0 or self.actual_tokens_used < 0:
            raise ValueError("latency/tokens must be non-negative")
        if self.entanglement_errors < 0:
            raise ValueError("entanglement_errors must be non-negative")


class CFOHaltError(Exception):
    """No Flow Unit fits the CFO budget — trigger muscle-memory fallback."""

    def __init__(self, budget: int, unit_count: int) -> None:
        self.budget = budget
        self.unit_count = unit_count
        super().__init__(
            f"CFO Halt: No Flow Units available within budget={budget} "
            f"(candidates={unit_count}). Triggering Muscle-Memory fallback."
        )


class ReferenceQuantumRouter:
    """Measurement operator M — collapses playbook options to one Flow Unit."""

    def __init__(
        self,
        alpha: float = 1.0,
        beta: float = 0.5,
        gamma: float = 0.8,
        temperature: float = 1.0,
    ) -> None:
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.temperature = max(1e-6, temperature)
        self.last_collapse: Optional[Dict[str, object]] = None

    def calculate_entanglement(
        self,
        structural_errors: int,
        k: float = 0.5,
    ) -> float:
        return math.exp(-k * max(0, structural_errors))

    def unit_score(self, unit: TypedFlowUnit, context_entropy: float) -> float:
        h = max(0.0, min(1.0, context_entropy))
        history = unit.historical_success_rate * 0.7
        entropy_term = (
            unit.handles_uncertainty * h
            + (1.0 - unit.handles_uncertainty) * (1.0 - h)
        ) * 0.3
        return history + entropy_term

    def collapse_wave_function(
        self,
        context_entropy: float,
        available_units: Sequence[TypedFlowUnit],
        cfo_budget: int,
    ) -> TypedFlowUnit:
        valid_units = [
            u for u in available_units if u.avg_token_cost <= cfo_budget
        ]
        if not valid_units:
            raise CFOHaltError(cfo_budget, len(available_units))

        best_unit: Optional[TypedFlowUnit] = None
        highest_probability = -float("inf")
        scores: Dict[str, float] = {}

        for unit in valid_units:
            score = self.unit_score(unit, context_entropy)
            probability = math.exp(score / self.temperature)
            scores[unit.id] = probability
            if probability > highest_probability:
                highest_probability = probability
                best_unit = unit

        assert best_unit is not None
        total = sum(scores.values()) or 1.0
        self.last_collapse = {
            "chosen_id": best_unit.id,
            "description": best_unit.description,
            "context_entropy": round(context_entropy, 4),
            "cfo_budget": cfo_budget,
            "candidates": len(valid_units),
            "blocked": len(available_units) - len(valid_units),
            "probabilities": {
                uid: round(p / total, 4) for uid, p in scores.items()
            },
            "confidence": 1.0,
            "operator": "M = Charter @ RhythmMarker",
        }
        return best_unit


QuantumRouter = ReferenceQuantumRouter


class WorkerAgent:
    """Operational Key Player with patched fitness telemetry."""

    def __init__(self, agent_id: str, role: str) -> None:
        self.agent_id = agent_id
        self.role = role
        self.fitness = AgentFitness()
        self.status = "ACTIVE"
        self.termination_risk_index = 0.0

    def calculate_overall_fitness(self, router: ReferenceQuantumRouter) -> float:
        """Patched F(x): bloat penalty + bounded speed (no 1/Δt blow-up)."""
        f = self.fitness
        overall = reference_node_fitness(
            q_success=f.q_success,
            q_total=f.q_total,
            actual_latency_ms=f.actual_latency_ms,
            actual_tokens=f.actual_tokens_used,
            expected_tokens=f.expected_tokens,
            expected_latency_ms=f.expected_latency_ms,
            entanglement_errors=f.entanglement_errors,
            alpha=router.alpha,
            beta=router.beta,
            gamma=router.gamma,
        )
        self.termination_risk_index = risk_from_fitness(overall)
        return overall

    def record_execution(
        self,
        *,
        success: bool,
        delta_t_ms: float,
        tokens: int,
        entanglement_errors: int = 0,
        expected_tokens: Optional[int] = None,
        expected_latency_ms: Optional[float] = None,
    ) -> None:
        self.fitness.q_total += 1
        if success:
            self.fitness.q_success += 1
        if self.fitness.q_total > 1:
            self.fitness.actual_latency_ms = (
                self.fitness.actual_latency_ms + delta_t_ms
            ) / 2.0
        else:
            self.fitness.actual_latency_ms = delta_t_ms
        self.fitness.actual_tokens_used += tokens
        if expected_tokens is not None:
            self.fitness.expected_tokens = expected_tokens
        else:
            self.fitness.expected_tokens = max(
                self.fitness.expected_tokens, tokens
            )
        if expected_latency_ms is not None:
            self.fitness.expected_latency_ms = expected_latency_ms
        self.fitness.entanglement_errors += max(0, entanglement_errors)
        self.fitness.delta_t_ms = self.fitness.actual_latency_ms
        self.fitness.total_tokens = self.fitness.actual_tokens_used


class BossAgent:
    """General Manager — QuantumRouter + roster + Monday Morning Sync."""

    def __init__(
        self,
        name: str = "Alpha-GM",
        router: Optional[ReferenceQuantumRouter] = None,
        *,
        quiet: bool = True,
    ) -> None:
        self.name = name
        self.router = router or ReferenceQuantumRouter()
        self.roster: Dict[str, WorkerAgent] = {}
        self.playbook: List[str] = []
        self.quiet = quiet
        if not quiet:
            print(f"[System] Boss Agent ({name}) Initialized.")

    def add_agent(self, agent: WorkerAgent) -> None:
        self.roster[agent.agent_id] = agent

    def monday_morning_sync(self) -> Dict[str, object]:
        if not self.quiet:
            print("\n" + "=" * 50)
            print("INITIATING MONDAY MORNING SYNC (Downtime Telemetry Review)")
            print("=" * 50)

        fitness_scores: Dict[str, float] = {}
        for a_id, agent in self.roster.items():
            if agent.status == "FIRED":
                continue
            score = agent.calculate_overall_fitness(self.router)
            fitness_scores[a_id] = score
            if not self.quiet:
                print(
                    f"Agent {a_id} | Role: {agent.role} | "
                    f"Fitness Score: {score:.3f} | "
                    f"Risk: {agent.termination_risk_index:.2f}"
                )

        outcomes: Dict[str, str] = {}
        avg_score = (
            sum(fitness_scores.values()) / max(1, len(fitness_scores))
            if fitness_scores
            else 0.0
        )

        for a_id, score in fitness_scores.items():
            agent = self.roster[a_id]
            if (
                score < (avg_score * 0.7)
                or agent.fitness.entanglement_errors > 3
            ):
                self.roster[a_id].status = "FIRED"
                outcomes[a_id] = "FIRED"
                msg = (
                    f"FIRE: Agent {a_id} below industry benchmarks "
                    f"(F={score:.3f} < 0.7×avg={avg_score:.3f})"
                )
                self.playbook.append(msg)
                if not self.quiet:
                    print(f"   {msg}")
            elif score > (avg_score * 1.3):
                self.roster[a_id].status = "PROMOTED"
                outcomes[a_id] = "PROMOTED"
                msg = f"PROMOTE: Agent {a_id} (F={score:.3f})"
                self.playbook.append(msg)
                if not self.quiet:
                    print(f"   {msg}")
            else:
                outcomes[a_id] = "RETAINED"

        if not self.quiet:
            print("Sync complete. Bar raised.")
        return {
            "outcomes": outcomes,
            "fitness_scores": {
                k: round(v, 4) for k, v in fitness_scores.items()
            },
            "avg_score": round(avg_score, 4),
            "playbook": list(self.playbook),
        }


def default_playbook() -> List[TypedFlowUnit]:
    return [
        TypedFlowUnit(
            id="U1",
            description="Standard Ingest + Schema Enforce",
            historical_success_rate=0.92,
            avg_token_cost=180,
            handles_uncertainty=0.2,
            expected_latency_ms=120.0,
        ),
        TypedFlowUnit(
            id="U2",
            description="Lite Path",
            historical_success_rate=0.85,
            avg_token_cost=90,
            handles_uncertainty=0.1,
            expected_latency_ms=80.0,
        ),
        TypedFlowUnit(
            id="U3",
            description="Data Cleansing for high entropy",
            historical_success_rate=0.88,
            avg_token_cost=340,
            handles_uncertainty=0.95,
            expected_latency_ms=400.0,
        ),
    ]


def apply_reference_telemetry(gm: BossAgent) -> None:
    """Seed roster with audit-patch demo telemetry.

    A1 — schema errors (should FIRE)
    A2 — heavy legitimate work (should RETAIN under delta-token)
    A3 — high quality (should PROMOTE)
    """
    a1 = gm.roster.get("A1")
    a2 = gm.roster.get("A2")
    a3 = gm.roster.get("A3")
    if a1:
        a1.fitness = AgentFitness(
            q_success=20,
            q_total=50,
            actual_latency_ms=800.0,
            actual_tokens_used=400,
            expected_tokens=200,
            expected_latency_ms=100.0,
            entanglement_errors=4,
            delta_t_ms=800.0,
            total_tokens=400,
        )
    if a2:
        a2.fitness = AgentFitness(
            q_success=45,
            q_total=50,
            actual_latency_ms=450.0,
            actual_tokens_used=2050,
            expected_tokens=2000,
            expected_latency_ms=400.0,
            entanglement_errors=0,
            delta_t_ms=450.0,
            total_tokens=2050,
        )
    if a3:
        a3.fitness = AgentFitness(
            q_success=49,
            q_total=50,
            actual_latency_ms=90.0,
            actual_tokens_used=400,
            expected_tokens=400,
            expected_latency_ms=100.0,
            entanglement_errors=0,
            delta_t_ms=90.0,
            total_tokens=400,
        )


def run_reference_simulation(*, quiet: bool = True) -> Dict[str, object]:
    """Canonical sim with patched fitness (heavy worker not wrongly fired)."""
    boss = BossAgent(quiet=quiet)
    a1 = WorkerAgent("A1", "Data Cleanser")
    a2 = WorkerAgent("A2", "Code Generator")
    a3 = WorkerAgent("A3", "QA Validator")
    boss.add_agent(a1)
    boss.add_agent(a2)
    boss.add_agent(a3)
    apply_reference_telemetry(boss)

    playbook = default_playbook()
    router = boss.router
    u_low = router.collapse_wave_function(0.1, playbook, cfo_budget=500)
    u_high = router.collapse_wave_function(0.9, playbook, cfo_budget=500)

    sync = boss.monday_morning_sync()
    return {
        "chosen_path": {"id": u_low.id, "description": u_low.description},
        "messy_path": {"id": u_high.id, "description": u_high.description},
        "low_entropy_unit": u_low.id,
        "high_entropy_unit": u_high.id,
        "sync": sync,
        "roster_status": {aid: a.status for aid, a in boss.roster.items()},
        "a2_fitness": a2.calculate_overall_fitness(router),
        "a2_not_fired_for_hard_work": sync["outcomes"].get("A2") != "FIRED",
        "a1_fired_for_errors": sync["outcomes"].get("A1") == "FIRED",
    }
