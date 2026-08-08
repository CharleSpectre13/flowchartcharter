"""Patched fitness math — Audit V1 (delta-token) + V2 (bounded speed).

Critical fixes:
  V1 Token Penalty Trap → only penalize bloat (actual − expected)
  V2 Speed divide-by-zero → β · exp(−actual/expected), capped contribution
"""

from __future__ import annotations

import math
from typing import Sequence

from .metrics import ExecutionMetrics

DEFAULT_ALPHA = 0.4
DEFAULT_BETA = 0.3
DEFAULT_GAMMA = 0.15  # weight on token *bloat* (not absolute spend)
DEFAULT_DELTA = 0.2  # Q_entanglement / synergy
COST_NORM = 300.0  # bloat normalization scale
DEFAULT_EXPECTED_LATENCY = 1.0  # seconds when metric omits expected_time
DEFAULT_EXPECTED_TOKENS = 300
INDUSTRY_BENCHMARK = 0.65

# Reference-engine scale coefficients (WorkerNode / AgentFitness style)
REF_ALPHA = 1.0
REF_BETA = 0.5
REF_GAMMA = 0.8
BLOAT_NORM = 1000.0
DEFAULT_EXPECTED_LATENCY_MS = 100.0


def speed_score(
    actual_time: float,
    expected_time: float,
    *,
    beta: float = DEFAULT_BETA,
) -> float:
    """Bounded exponential decay — max contribution = beta (never blows up).

    Speed_Score = β · exp(−actual / expected)
    As actual → 0, score → β (not ∞).
    """
    exp_t = expected_time if expected_time > 0 else DEFAULT_EXPECTED_LATENCY
    actual = max(0.0, float(actual_time))
    return beta * math.exp(-actual / exp_t)


def token_bloat_penalty(
    actual_tokens: float,
    expected_tokens: float,
    *,
    gamma: float = DEFAULT_GAMMA,
    norm: float = COST_NORM,
) -> float:
    """Delta-token penalty — only bloat hurts.

    Token_Penalty = γ · max(0, actual − expected) / norm
    """
    expected = expected_tokens if expected_tokens > 0 else float(actual_tokens)
    bloat = max(0.0, float(actual_tokens) - float(expected))
    return gamma * (bloat / max(norm, 1e-9))


def fitness(
    history: Sequence[ExecutionMetrics],
    *,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
    delta: float = DEFAULT_DELTA,
) -> float:
    """Monday Morning Sync fitness (patched).

    F(x) = α·(Q_success/Q_total)
         + β·exp(−Δt / expected_t)
         − γ·max(0, tokens − expected_tokens)/norm
         + δ·Q_entanglement

    Does **not** punish legitimate heavy-compute work that stays on budget.
    Does **not** explode when Muscle-Memory replay is near-instant.
    """
    if not history:
        return 0.0
    n = len(history)
    avg_q = sum(m.quality_score for m in history) / n
    avg_t = sum(m.execution_time for m in history) / n
    avg_c = sum(m.token_cost for m in history) / n
    avg_s = sum(m.synergy_score for m in history) / n
    avg_exp_t = (
        sum((m.expected_time if m.expected_time > 0 else DEFAULT_EXPECTED_LATENCY) for m in history)
        / n
    )
    avg_exp_c = (
        sum(
            (m.expected_token_cost if m.expected_token_cost > 0 else DEFAULT_EXPECTED_TOKENS)
            for m in history
        )
        / n
    )

    q_term = alpha * avg_q
    speed_term = speed_score(avg_t, avg_exp_t, beta=beta)
    cost_term = token_bloat_penalty(avg_c, avg_exp_c, gamma=gamma)
    synergy_term = delta * avg_s
    return q_term + speed_term - cost_term + synergy_term


def fitness_components(
    history: Sequence[ExecutionMetrics],
    **kwargs: float,
) -> dict:
    """Breakdown for audits / telemetry (tensor-stable components)."""
    if not history:
        return {
            "quality": 0.0,
            "speed": 0.0,
            "bloat_penalty": 0.0,
            "synergy": 0.0,
            "total": 0.0,
        }
    alpha = kwargs.get("alpha", DEFAULT_ALPHA)
    beta = kwargs.get("beta", DEFAULT_BETA)
    gamma = kwargs.get("gamma", DEFAULT_GAMMA)
    delta = kwargs.get("delta", DEFAULT_DELTA)
    n = len(history)
    avg_q = sum(m.quality_score for m in history) / n
    avg_t = sum(m.execution_time for m in history) / n
    avg_c = sum(m.token_cost for m in history) / n
    avg_s = sum(m.synergy_score for m in history) / n
    avg_exp_t = (
        sum((m.expected_time if m.expected_time > 0 else DEFAULT_EXPECTED_LATENCY) for m in history)
        / n
    )
    avg_exp_c = (
        sum(
            (m.expected_token_cost if m.expected_token_cost > 0 else DEFAULT_EXPECTED_TOKENS)
            for m in history
        )
        / n
    )
    return {
        "quality": alpha * avg_q,
        "speed": speed_score(avg_t, avg_exp_t, beta=beta),
        "bloat_penalty": token_bloat_penalty(avg_c, avg_exp_c, gamma=gamma),
        "synergy": delta * avg_s,
        "total": fitness(history, alpha=alpha, beta=beta, gamma=gamma, delta=delta),
        "avg_actual_tokens": avg_c,
        "avg_expected_tokens": avg_exp_c,
        "avg_actual_time": avg_t,
        "avg_expected_time": avg_exp_t,
    }


def reference_node_fitness(
    *,
    q_success: int,
    q_total: int,
    actual_latency_ms: float,
    actual_tokens: int,
    expected_tokens: int,
    expected_latency_ms: float = DEFAULT_EXPECTED_LATENCY_MS,
    entanglement_errors: int = 0,
    alpha: float = REF_ALPHA,
    beta: float = REF_BETA,
    gamma: float = REF_GAMMA,
) -> float:
    """WorkerNode / AgentFitness formula from audit patch engine.

    overall = α·(q_s/q_t) + β·exp(−lat/exp_lat)
              − γ·bloat/1000 + exp(−0.5·errors)
    """
    q_score = alpha * (q_success / max(1, q_total))
    speed_ratio = actual_latency_ms / max(1.0, expected_latency_ms)
    speed = beta * math.exp(-speed_ratio)
    bloat = max(0, actual_tokens - expected_tokens)
    cost_penalty = gamma * (bloat / BLOAT_NORM)
    synergy = math.exp(-0.5 * max(0, entanglement_errors))
    return q_score + speed - cost_penalty + synergy


def risk_from_fitness(overall_fitness: float, *, ceiling: float = 3.0) -> float:
    """Invert fitness → termination_risk_index (TPC)."""
    return max(0.0, ceiling - overall_fitness)
