from __future__ import annotations

from typing import Sequence

from .metrics import ExecutionMetrics

DEFAULT_ALPHA = 0.4
DEFAULT_BETA = 0.3
DEFAULT_GAMMA = 0.15  # weight on mean-normalized token cost
DEFAULT_DELTA = 0.2  # Q_entanglement / synergy
COST_NORM = 300.0  # reference mean tokens per flow unit
INDUSTRY_BENCHMARK = 0.65


def fitness(
    history: Sequence[ExecutionMetrics],
    *,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
    delta: float = DEFAULT_DELTA,
) -> float:
    """Fear-accountable fitness used at Monday Morning Sync.

    F(x) = α·(Q_success/Q_total) + β·(1/Δt) − γ·Tokens_norm + Q_entanglement

    Q_success/Q_total approximated as mean quality_score over history.
    Tokens mean-normalized by COST_NORM so short runs do not mass-fire.
    Q_entanglement = mean synergy_score.
    """
    if not history:
        return 0.0
    n = len(history)
    avg_q = sum(m.quality_score for m in history) / n
    avg_t = sum(m.execution_time for m in history) / n
    avg_c = sum(m.token_cost for m in history) / n
    avg_s = sum(m.synergy_score for m in history) / n
    rhythm = (1.0 / avg_t) if avg_t > 0 else 0.0
    cost_norm = avg_c / COST_NORM
    return (alpha * avg_q) + (beta * rhythm) - (gamma * cost_norm) + (delta * avg_s)
