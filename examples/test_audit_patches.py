#!/usr/bin/env python3
"""Audit V1–V3 patches: delta-token, bounded speed, phantom elastic requisition."""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.fitness import (  # noqa: E402
    fitness,
    speed_score,
    token_bloat_penalty,
    reference_node_fitness,
)
from flowchartcharter.metrics import ExecutionMetrics  # noqa: E402
from flowchartcharter.reference_engine import (  # noqa: E402
    run_reference_simulation,
)
from flowchartcharter import FlowChartCharterSystem  # noqa: E402


def test_v1_delta_token_no_punish_hard_work() -> None:
    """Heavy 2000-token job with expected 2000 → near-zero penalty."""
    p_on_budget = token_bloat_penalty(2000, 2000, gamma=0.8, norm=1000)
    p_bloated = token_bloat_penalty(3000, 2000, gamma=0.8, norm=1000)
    assert p_on_budget == 0.0
    assert p_bloated > 0.0
    heavy = [
        ExecutionMetrics(
            2000, 1.5, 0.95, 0.9,
            expected_token_cost=2000, expected_time=1.5,
        )
    ]
    light_bloated = [
        ExecutionMetrics(
            400, 1.0, 0.95, 0.9,
            expected_token_cost=100, expected_time=1.0,
        )
    ]
    assert fitness(heavy) > fitness(light_bloated) - 0.5
    print("OK V1 delta-token", p_on_budget, p_bloated, fitness(heavy))


def test_v2_speed_bounded_no_div_zero() -> None:
    """Near-instant execution must not explode fitness."""
    instant = speed_score(0.001, 1.0, beta=0.5)
    normal = speed_score(1.0, 1.0, beta=0.5)
    slow = speed_score(10.0, 1.0, beta=0.5)
    assert instant <= 0.5 + 1e-9
    assert instant > normal > slow
    assert math.isfinite(instant)
    hist = [
        ExecutionMetrics(
            100, 0.001, 0.9, 0.9,
            expected_token_cost=100, expected_time=1.0,
        )
    ]
    f = fitness(hist)
    assert math.isfinite(f) and f < 10.0
    print("OK V2 bounded speed", instant, normal, f)


def test_v3_phantom_elastic() -> None:
    system = FlowChartCharterSystem(seed=2)
    r = system.execute_charter(
        "Novel sql_optimization for warehouse queries",
        force_capability="sql_optimization",
    )
    assert r["phantom_spawned"] is not None
    assert "sql_optimization" in system.elastic.known_capabilities
    sync = system.downtime_sync()
    assert "elastic" in sync
    assert "phantom_outcomes" in sync
    print(
        "OK V3 phantom",
        r["phantom_spawned"],
        sync.get("phantom_outcomes"),
        system.elastic.export()["known_capabilities"],
    )


def test_reference_engine_heavy_not_fired() -> None:
    result = run_reference_simulation(quiet=True)
    assert result["a2_not_fired_for_hard_work"] is True
    assert result["a1_fired_for_errors"] is True
    assert math.isfinite(float(result["a2_fitness"]))
    print(
        "OK reference sim",
        result["sync"]["outcomes"],
        "A2 F=",
        result["a2_fitness"],
    )


def test_reference_node_formula() -> None:
    f = reference_node_fitness(
        q_success=45,
        q_total=50,
        actual_latency_ms=450,
        actual_tokens=2050,
        expected_tokens=2000,
        expected_latency_ms=400,
        entanglement_errors=0,
    )
    assert f > 1.0
    f_bad = reference_node_fitness(
        q_success=10,
        q_total=50,
        actual_latency_ms=2000,
        actual_tokens=3000,
        expected_tokens=500,
        entanglement_errors=5,
    )
    assert f_bad < f
    print("OK reference_node_fitness", round(f, 3), round(f_bad, 3))


if __name__ == "__main__":
    test_v1_delta_token_no_punish_hard_work()
    test_v2_speed_bounded_no_div_zero()
    test_reference_node_formula()
    test_reference_engine_heavy_not_fired()
    test_v3_phantom_elastic()
    print("ALL_AUDIT_PATCH_TESTS_PASSED")
