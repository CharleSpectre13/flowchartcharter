from __future__ import annotations
from typing import Sequence
from .metrics import ExecutionMetrics

DEFAULT_ALPHA = 0.4
DEFAULT_BETA = 0.3
DEFAULT_GAMMA = 0.001
DEFAULT_DELTA = 0.2
INDUSTRY_BENCHMARK = 0.65


def fitness(
    history: Sequence[ExecutionMetrics],
    *,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
    delta: float = DEFAULT_DELTA,
) -> float:
    """F = α·Quality + β·Rhythm − γ·Cost + δ·Synergy"""
    if not history:
        return 0.0
    n = len(history)
    avg_q = sum(m.quality_score for m in history) / n
    avg_t = sum(m.execution_time for m in history) / n
    avg_c = sum(m.token_cost for m in history) / n
    avg_s = sum(m.synergy_score for m in history) / n
    rhythm = (1.0 / avg_t) if avg_t > 0 else 0.0
    return (alpha * avg_q) + (beta * rhythm) - (gamma * avg_c) + (delta * avg_s)
