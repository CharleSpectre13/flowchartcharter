#!/usr/bin/env python3
"""Tests for the Architectural Reference engine (PEP8-clean, audit-patched)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.reference_engine import (  # noqa: E402
    AgentFitness,
    BossAgent,
    CFOHaltError,
    ReferenceQuantumRouter,
    TypedFlowUnit,
    WorkerAgent,
    apply_reference_telemetry,
    default_playbook,
    run_reference_simulation,
)
from flowchartcharter.fitness import reference_node_fitness  # noqa: E402


def test_flow_unit_validation() -> None:
    try:
        TypedFlowUnit("bad", "x", 1.5, 10)
        raise AssertionError("should reject success_rate > 1")
    except ValueError:
        pass
    unit = TypedFlowUnit("U", "ok", 0.9, 100)
    assert unit.handles_uncertainty == 0.5
    print("OK FlowUnit validation")


def test_entanglement() -> None:
    router = ReferenceQuantumRouter()
    assert abs(router.calculate_entanglement(0) - 1.0) < 1e-12
    assert router.calculate_entanglement(10) < 0.01
    print("OK entanglement", round(router.calculate_entanglement(2), 4))


def test_collapse_filters_cfo() -> None:
    router = ReferenceQuantumRouter()
    units = default_playbook()
    chosen = router.collapse_wave_function(0.2, units, cfo_budget=1000)
    assert chosen.avg_token_cost <= 1000
    assert chosen.id == "U1"
    assert router.last_collapse is not None
    assert router.last_collapse["confidence"] == 1.0
    print("OK collapse", chosen.id)


def test_cfo_halt() -> None:
    router = ReferenceQuantumRouter()
    units = [TypedFlowUnit("X", "expensive", 0.9, 99999)]
    try:
        router.collapse_wave_function(0.1, units, cfo_budget=10)
        raise AssertionError("expected CFOHaltError")
    except CFOHaltError as exc:
        assert exc.budget == 10
    print("OK CFOHaltError")


def test_high_entropy_prefers_cleansing() -> None:
    router = ReferenceQuantumRouter()
    units = default_playbook()
    messy = router.collapse_wave_function(0.95, units, cfo_budget=1000)
    assert messy.id == "U3"
    print("OK high H_ctx →", messy.id)


def test_fitness_formula_patched() -> None:
    """Patched math: perfect quality, on-budget tokens, nominal latency."""
    router = ReferenceQuantumRouter(alpha=1.0, beta=0.5, gamma=0.8)
    worker = WorkerAgent("T", "Tester")
    worker.fitness = AgentFitness(
        q_success=50,
        q_total=50,
        actual_latency_ms=100.0,
        actual_tokens_used=500,
        expected_tokens=500,
        expected_latency_ms=100.0,
        entanglement_errors=0,
        delta_t_ms=100.0,
        total_tokens=500,
    )
    score = worker.calculate_overall_fitness(router)
    expected = reference_node_fitness(
        q_success=50,
        q_total=50,
        actual_latency_ms=100.0,
        actual_tokens=500,
        expected_tokens=500,
        expected_latency_ms=100.0,
        entanglement_errors=0,
        alpha=1.0,
        beta=0.5,
        gamma=0.8,
    )
    assert abs(score - expected) < 1e-9
    assert math.isfinite(score)
    # near-instant must stay bounded
    worker.fitness.actual_latency_ms = 0.001
    worker.fitness.delta_t_ms = 0.001
    fast = worker.calculate_overall_fitness(router)
    assert math.isfinite(fast) and fast < 5.0
    print("OK fitness patched", round(score, 3), round(fast, 3))


def test_monday_morning_sync() -> None:
    """A2 heavy work RETAINED; A1 schema errors FIRED; A3 PROMOTED."""
    gm = BossAgent(quiet=True)
    gm.add_agent(WorkerAgent("A1", "Data Cleanser"))
    gm.add_agent(WorkerAgent("A2", "Code Generator"))
    gm.add_agent(WorkerAgent("A3", "QA Validator"))
    apply_reference_telemetry(gm)

    sync = gm.monday_morning_sync()
    assert sync["outcomes"]["A1"] == "FIRED"
    assert sync["outcomes"]["A2"] != "FIRED"  # delta-token protects hard work
    assert sync["outcomes"]["A3"] == "PROMOTED"
    print("OK monday sync", sync["outcomes"])


def test_full_simulation() -> None:
    result = run_reference_simulation(quiet=True)
    assert result["chosen_path"]["id"] == "U1"
    assert result["roster_status"]["A2"] != "FIRED"
    assert result["roster_status"]["A1"] == "FIRED"
    assert result["roster_status"]["A3"] == "PROMOTED"
    assert result["messy_path"]["id"] == "U3"
    print("OK full simulation")


if __name__ == "__main__":
    test_flow_unit_validation()
    test_entanglement()
    test_collapse_filters_cfo()
    test_cfo_halt()
    test_high_entropy_prefers_cleansing()
    test_fitness_formula_patched()
    test_monday_morning_sync()
    test_full_simulation()
    print("ALL_REFERENCE_ENGINE_TESTS_PASSED")
