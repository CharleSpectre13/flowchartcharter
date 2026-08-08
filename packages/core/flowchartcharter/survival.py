"""Fear-Based Accountability & Survival Mechanism.

Models agent "fear" as an algorithmic penalty amplifier — not emotion.

Components:
  1. Cognitive Survival Constraint  — survival_status + termination_risk_index
  2. Error Accumulation Telemetry Ledger — immutable per-cycle metrics
  3. Monday Pruning + Lean Re-hiring — FIRE without automatic backfill
  4. Dynamic prompt injection — live risk drives generation parameters
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Thresholds (tunable, deterministic defaults)
# ---------------------------------------------------------------------------

RISK_SCHEMA_SPIKE = 0.18
RISK_TOKEN_SPIKE = 0.12
RISK_LATENCY_SPIKE = 0.08
RISK_DRIFT_SPIKE = 0.15
RISK_DECAY_ON_CLEAN = 0.04
RISK_FIRE_HARD = 0.85  # instant fire if risk breaches this at sync
ERROR_LEDGER_FIRE = 5  # cumulative schema errors before hard fire
TOKEN_CEILING_RATIO = 1.15  # spend / budget assignment


class SurvivalStatus(str, Enum):
    ACTIVE = "ACTIVE"
    AT_RISK = "AT_RISK"
    CRITICAL = "CRITICAL"
    TERMINATED = "TERMINATED"


@dataclass
class GenerationParameters:
    """LLM generation knobs forced by survival pressure."""

    temperature: float = 0.7
    top_p: float = 0.95
    max_tokens: int = 2048
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    schema_lock: bool = False
    creativity_cap: float = 1.0  # 0 = pure deterministic adherence

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LedgerEntry:
    """Immutable telemetry row for one execution cycle."""

    cycle_id: str
    schema_divergence: int
    token_spend: int
    token_ceiling: int
    delta_t: float
    structural_drift: float
    quality: float
    path: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TelemetryLedger:
    """Append-only error / cost / latency ledger."""

    entries: List[LedgerEntry] = field(default_factory=list)

    def commit(self, entry: LedgerEntry) -> None:
        self.entries.append(entry)

    @property
    def schema_errors(self) -> int:
        return sum(e.schema_divergence for e in self.entries)

    @property
    def total_tokens(self) -> int:
        return sum(e.token_spend for e in self.entries)

    @property
    def mean_delta_t(self) -> float:
        if not self.entries:
            return 0.0
        return sum(e.delta_t for e in self.entries) / len(self.entries)

    @property
    def over_budget_count(self) -> int:
        return sum(
            1
            for e in self.entries
            if e.token_ceiling > 0 and e.token_spend > e.token_ceiling
        )

    def export(self) -> Dict[str, Any]:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "schema_errors": self.schema_errors,
            "total_tokens": self.total_tokens,
            "mean_delta_t": round(self.mean_delta_t, 4),
            "over_budget_count": self.over_budget_count,
            "cycles": len(self.entries),
        }


def risk_from_ledger(
    ledger: TelemetryLedger,
    *,
    prior_risk: float = 0.0,
) -> float:
    """Compute termination_risk_index ∈ [0, 1] from immutable ledger."""
    risk = max(0.0, min(1.0, prior_risk))
    if not ledger.entries:
        return risk
    last = ledger.entries[-1]
    if last.schema_divergence > 0:
        risk += RISK_SCHEMA_SPIKE * last.schema_divergence
    if last.token_ceiling > 0 and last.token_spend > last.token_ceiling:
        over = (last.token_spend / last.token_ceiling) - 1.0
        risk += RISK_TOKEN_SPIKE * (1.0 + over)
    if last.delta_t > 2.0:
        risk += RISK_LATENCY_SPIKE * min(2.0, last.delta_t / 2.0)
    if last.structural_drift > 0.25:
        risk += RISK_DRIFT_SPIKE * last.structural_drift
    if (
        last.schema_divergence == 0
        and last.structural_drift < 0.1
        and last.quality >= 0.9
    ):
        risk = max(0.0, risk - RISK_DECAY_ON_CLEAN)
    return max(0.0, min(1.0, risk))


def status_from_risk(risk: float) -> SurvivalStatus:
    if risk >= RISK_FIRE_HARD:
        return SurvivalStatus.CRITICAL
    if risk >= 0.55:
        return SurvivalStatus.AT_RISK
    return SurvivalStatus.ACTIVE


def generation_params_for_risk(risk: float) -> GenerationParameters:
    """Map termination_risk_index → generation parameters.

    Higher risk → lower temperature, hard schema_lock, shorter max_tokens.
    Forces deterministic adherence over creative guesswork.
    """
    risk = max(0.0, min(1.0, risk))
    temperature = max(0.0, 0.7 * (1.0 - risk))
    top_p = max(0.2, 0.95 * (1.0 - 0.6 * risk))
    max_tokens = int(2048 * (1.0 - 0.55 * risk))
    max_tokens = max(256, max_tokens)
    schema_lock = risk >= 0.35
    creativity_cap = max(0.0, 1.0 - risk)
    return GenerationParameters(
        temperature=round(temperature, 4),
        top_p=round(top_p, 4),
        max_tokens=max_tokens,
        frequency_penalty=round(0.4 * risk, 4),
        presence_penalty=round(0.3 * risk, 4),
        schema_lock=schema_lock,
        creativity_cap=round(creativity_cap, 4),
    )


def build_worker_system_prompt(
    *,
    agent_name: str,
    role: str,
    survival_status: str,
    termination_risk_index: float,
    generation: GenerationParameters,
    schema_errors: int = 0,
    flow_unit_schema: Optional[str] = None,
) -> str:
    """Dynamic worker system prompt with persistent survival telemetry."""
    schema_block = flow_unit_schema or (
        "{result: str, quality: float, path: str, tokens: int}"
    )
    fear_block = ""
    if termination_risk_index >= 0.35:
        fear_block = f"""
[SURVIVAL PRESSURE — ACTIVE]
Your termination_risk_index is elevated ({termination_risk_index:.3f}).
You MUST:
- Prioritize strict deterministic adherence to the Flow Unit schema.
- Suppress creative, open-ended, token-bloated guesswork.
- Output ONLY schema-valid JSON. No conversational filler.
- Prefer Muscle-Memory precedent over novel reasoning.
Schema lock: {generation.schema_lock}
Creativity cap: {generation.creativity_cap}
"""
    return f"""[WORKER SYSTEM PROMPT BEGIN]
Role: {role}
Agent: {agent_name}
Objective: Execute assigned Flow Units with absolute schema fidelity.
Directive: Charter-first. Never invent paths outside the approved playbook.

[PERSISTENT TELEMETRY STATE]
survival_status = {survival_status}
termination_risk_index = {termination_risk_index:.4f}
schema_divergence_count = {schema_errors}
generation_temperature = {generation.temperature}
generation_top_p = {generation.top_p}
generation_max_tokens = {generation.max_tokens}
schema_lock = {generation.schema_lock}
{fear_block}
[FLOW UNIT SCHEMA]
{schema_block}

[RULES]
1. Blackboard JSON only — no natural language between agents.
2. On schema doubt: call EvaluateRhythmMarker before handoff.
3. On job familiarity: call QueryMuscleMemory before inventing steps.
4. Exceeding token ceiling escalates termination_risk_index.
5. Monday Morning Sync will FIRE agents with low fitness or high ledger errors.
[WORKER SYSTEM PROMPT END]"""


@dataclass
class LeanRehireDecision:
    """Result of post-termination backfill check."""

    agent_name: str
    fired: bool
    backfill: bool
    reason: str
    surviving_ops: int
    muscle_memory_records: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def lean_rehire_check(
    *,
    agent_name: str,
    surviving_ops: int,
    muscle_memory_records: int,
    min_ops: int = 1,
    min_memory: int = 1,
) -> LeanRehireDecision:
    """If survivors + Muscle-Memory can carry the load, do NOT backfill."""
    can_carry = surviving_ops >= min_ops and muscle_memory_records >= min_memory
    if can_carry:
        return LeanRehireDecision(
            agent_name=agent_name,
            fired=True,
            backfill=False,
            reason=(
                "Lean re-hire declined: surviving nodes + Muscle-Memory VDB "
                "can carry workload. Hierarchy permanently shrunk."
            ),
            surviving_ops=surviving_ops,
            muscle_memory_records=muscle_memory_records,
        )
    return LeanRehireDecision(
        agent_name=agent_name,
        fired=True,
        backfill=True,
        reason=(
            "Backfill required: insufficient surviving ops or empty "
            "Muscle-Memory coverage."
        ),
        surviving_ops=surviving_ops,
        muscle_memory_records=muscle_memory_records,
    )


def should_fire_from_ledger(
    risk: float,
    ledger: TelemetryLedger,
    fitness_score: float,
    *,
    fitness_floor: float,
) -> bool:
    """Hard fire predicates for Monday Sync."""
    if risk >= RISK_FIRE_HARD:
        return True
    if ledger.schema_errors >= ERROR_LEDGER_FIRE:
        return True
    if fitness_score < fitness_floor:
        return True
    return False
