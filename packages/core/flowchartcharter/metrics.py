from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionMetrics:
    """Per-cycle execution telemetry.

    ``expected_token_cost`` / ``expected_time`` enable delta-token bloat
    and bounded speed scoring (Audit patches V1 / V2).
    """

    token_cost: int
    execution_time: float
    quality_score: float
    synergy_score: float
    expected_token_cost: int = 0  # 0 → treat as equal to actual (zero bloat)
    expected_time: float = 0.0  # 0 → use DEFAULT_EXPECTED_LATENCY in fitness

    def __post_init__(self) -> None:
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("quality_score must be in [0, 1]")
        if not 0.0 <= self.synergy_score <= 1.0:
            raise ValueError("synergy_score must be in [0, 1]")
        if self.token_cost < 0 or self.execution_time < 0:
            raise ValueError("cost and time must be non-negative")
        if self.expected_token_cost < 0 or self.expected_time < 0:
            raise ValueError("expected cost/time must be non-negative")
