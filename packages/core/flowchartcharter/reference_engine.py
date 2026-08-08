"""FlowChartCharter reference engine — canonical blueprint simulation.

Implements the Architectural Reference (Wave Collapse + Monday Morning Sync)
with production hardening: typed schemas, CFO halt exception, PEP8 style,
and integration hooks into the full core package.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================


@dataclass
class TypedFlowUnit:
    """Playbook unit selected by wave-function collapse."""

    id: str
    description: str
    historical_success_rate: float
    avg_token_cost: int
    expected_input_schema: List[str] = field(default_factory=list)
    expected_output_schema: List[str] = field(default_factory=list)
    handles_uncertainty: float = 0.5  # 0=clean-only, 1=messy-data specialist

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
    """Telemetry counters for F(x) fitness scoring."""

    q_success: int = 1
    q_total: int = 1
    delta_t_ms: float = 100.0
    total_tokens: int = 500
    entanglement_errors: int = 0  # structural divergence count

    def __post_init__(self) -> None:
        if self.q_success < 0 or self.q_total < 0:
            raise ValueError("q_success/q_total must be non-negative")
        if self.delta_t_ms < 0 or self.total_tokens < 0:
            raise ValueError("delta_t_ms/total_tokens must be non-negative")
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


# =============================================================================
# QUANTUM-INSPIRED ROUTING ENGINE
# =============================================================================


class ReferenceQuantumRouter:
    """Measurement operator M — collapses playbook options to one Flow Unit.

    score = 0.7 * historical_success + 0.3 * entropy_match
    probability ∝ exp(score / temperature)
    """

    def __init__(
        self,
        alpha: float = 1.0,
        beta: float = 0.5,
        gamma: float = 0.2,
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
        """Q_entanglement = exp(−k · errors). Perfect synergy (0 errors) = 1.0."""
        return math.exp(-k * max(0, structural_errors))

    def unit_score(self, unit: TypedFlowUnit, context_entropy: float) -> float:
        """W_history * C + W_context * entropy affinity.

        High context entropy favors units with high handles_uncertainty.
        """
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
        """The Measurement: filter by CFO budget, then argmax scaled score."""
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

        assert best_unit is not None  # valid_units non-empty
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


# Alias matching the architectural reference name
QuantumRouter = ReferenceQuantumRouter


# =============================================================================
# CORPORATE HIERARCHY & DYNAMIC TALENT MANAGEMENT
# =============================================================================


class WorkerAgent:
    """Operational Key Player / Position Manager with fitness telemetry."""

    def __init__(self, agent_id: str, role: str) -> None:
        self.agent_id = agent_id
        self.role = role
        self.fitness = AgentFitness()
        self.status = "ACTIVE"  # ACTIVE | PROMOTED | FIRED | DEMOTED

    def calculate_overall_fitness(self, router: ReferenceQuantumRouter) -> float:
        """F(x) = α·(Q_s/Q_t) + β·(1000/Δt_ms) − γ·(tokens/1000) + Q_ent."""
        q_score = router.alpha * (
            self.fitness.q_success / max(1, self.fitness.q_total)
        )
        speed_score = router.beta * (
            1000.0 / max(1.0, self.fitness.delta_t_ms)
        )
        cost_penalty = router.gamma * (self.fitness.total_tokens / 1000.0)
        synergy = router.calculate_entanglement(
            self.fitness.entanglement_errors
        )
        return q_score + speed_score - cost_penalty + synergy

    def record_execution(
        self,
        *,
        success: bool,
        delta_t_ms: float,
        tokens: int,
        entanglement_errors: int = 0,
    ) -> None:
        """Update telemetry after a Flow Unit completes."""
        self.fitness.q_total += 1
        if success:
            self.fitness.q_success += 1
        if self.fitness.q_total > 1:
            self.fitness.delta_t_ms = (
                self.fitness.delta_t_ms + delta_t_ms
            ) / 2.0
        else:
            self.fitness.delta_t_ms = delta_t_ms
        self.fitness.total_tokens += tokens
        self.fitness.entanglement_errors += max(0, entanglement_errors)


class BossAgent:
    """General Manager — owns QuantumRouter + roster + Monday Morning Sync."""

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
        """Asynchronous RLAIF loop — evaluate team, raise the bar."""
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
                    f"Fitness Score: {score:.3f}"
                )

        outcomes: Dict[str, str] = {}
        avg_score = (
            sum(fitness_scores.values()) / max(1, len(fitness_scores))
            if fitness_scores
            else 0.0
        )

        for a_id, score in fitness_scores.items():
            if score < (avg_score * 0.7):
                self.roster[a_id].status = "FIRED"
                outcomes[a_id] = "FIRED"
                msg = (
                    f"FIRE: Agent {a_id} below industry benchmarks "
                    f"(F={score:.3f} < 0.7×avg={avg_score:.3f})"
                )
                self.playbook.append(msg)
                if not self.quiet:
                    print(msg)
            elif score > (avg_score * 1.3):
                self.roster[a_id].status = "PROMOTED"
                outcomes[a_id] = "PROMOTED"
                msg = (
                    f"PROMOTE: Agent {a_id} exceeding standards "
                    f"(F={score:.3f} > 1.3×avg={avg_score:.3f})"
                )
                self.playbook.append(msg)
                if not self.quiet:
                    print(msg)
            else:
                self.roster[a_id].status = "ACTIVE"
                outcomes[a_id] = "RETAINED"

        if not self.quiet:
            print(
                "Monday Morning Sync Complete. Bar has been raised. "
                "Awaiting Workloads."
            )

        return {
            "outcomes": outcomes,
            "fitness_scores": {
                k: round(v, 4) for k, v in fitness_scores.items()
            },
            "avg_score": round(avg_score, 4),
            "playbook": list(self.playbook),
        }


# =============================================================================
# SIMULATION HELPERS
# =============================================================================


def default_playbook() -> List[TypedFlowUnit]:
    """Standard vs expensive-RAG units used in the reference simulation."""
    return [
        TypedFlowUnit(
            id="U1",
            description="Standard Refactor",
            historical_success_rate=0.95,
            avg_token_cost=200,
            expected_input_schema=["source"],
            expected_output_schema=["refactored"],
            handles_uncertainty=0.3,
        ),
        TypedFlowUnit(
            id="U2",
            description="Deep Search RAG",
            historical_success_rate=0.60,
            avg_token_cost=5000,
            expected_input_schema=["query"],
            expected_output_schema=["chunks"],
            handles_uncertainty=0.85,
        ),
        TypedFlowUnit(
            id="U3",
            description="Data Cleansing Pass",
            historical_success_rate=0.88,
            avg_token_cost=350,
            expected_input_schema=["raw"],
            expected_output_schema=["clean"],
            handles_uncertainty=0.95,
        ),
        TypedFlowUnit(
            id="U4",
            description="Lite Fast Path",
            historical_success_rate=0.80,
            avg_token_cost=90,
            expected_input_schema=["source"],
            expected_output_schema=["ok"],
            handles_uncertainty=0.4,
        ),
    ]


def apply_reference_telemetry(gm: BossAgent) -> None:
    """Apply the exact architectural-reference workload telemetry deltas.

    Matches the pasted blueprint simulation:
      - QA Validator: +50 q_success (ratio spikes → promote)
      - Code Generator: +15 entanglement errors, +15000 tokens (→ fire)
    """
    gm.roster["A3"].fitness.q_success += 50
    gm.roster["A3"].fitness.entanglement_errors = 0

    gm.roster["A2"].fitness.entanglement_errors += 15
    gm.roster["A2"].fitness.total_tokens += 15000


def run_reference_simulation(*, quiet: bool = False) -> Dict[str, object]:
    """End-to-end reference demo: roster → collapse → Monday Morning Sync."""
    gm = BossAgent(quiet=quiet)

    gm.add_agent(WorkerAgent("A1", "Data Cleanser"))
    gm.add_agent(WorkerAgent("A2", "Code Generator"))
    gm.add_agent(WorkerAgent("A3", "QA Validator"))

    apply_reference_telemetry(gm)

    available_units = default_playbook()
    cfo_budget = 1000
    context_entropy = 0.2

    if not quiet:
        print("\n[Rhythm Marker Reached] Calculating Next Flow Unit...")

    next_path = gm.router.collapse_wave_function(
        context_entropy,
        available_units,
        cfo_budget,
    )
    clear_collapse = dict(gm.router.last_collapse or {})

    if not quiet:
        print(
            f"Wave Collapsed. Selected Deterministic Path: "
            f"{next_path.id} - {next_path.description}"
        )

    sync = gm.monday_morning_sync()

    # High-entropy collapse should prefer cleansing (U3)
    messy = gm.router.collapse_wave_function(
        0.9,
        available_units,
        cfo_budget,
    )
    messy_collapse = dict(gm.router.last_collapse or {})

    return {
        "chosen_path": {
            "id": next_path.id,
            "description": next_path.description,
        },
        "collapse": clear_collapse,
        "messy_path": {"id": messy.id, "description": messy.description},
        "messy_collapse": messy_collapse,
        "sync": sync,
        "roster_status": {
            a_id: a.status for a_id, a in gm.roster.items()
        },
    }
