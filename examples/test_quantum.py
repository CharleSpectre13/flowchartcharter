#!/usr/bin/env python3
"""Unit tests for quantum routing — superposition, collapse, reinforce, H_ctx, CFO."""
from __future__ import annotations
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.quantum import (
    QuantumRouter,
    build_superposition,
    measure,
    reinforce,
    entanglement_score,
    quantum_path_select,
    contextual_entropy,
    PATH_STANDARD,
    PATH_CLEANSING,
    PATH_LITE,
)


def test_superposition_normalized():
    # equal affinity context → pure muscle weights (context_entropy mid-matched)
    # Use paths with same affinity to isolate weight ratio: force only two paths with equal affinity
    psi = build_superposition(
        [PATH_STANDARD, PATH_CLEANSING],
        {PATH_STANDARD: 3.0, PATH_CLEANSING: 1.0},
        context_entropy=0.0,  # low entropy favors standard further
    )
    probs = [a.probability for a in psi.amplitudes]
    assert abs(sum(probs) - 1.0) < 1e-9
    assert psi.dominant().path == PATH_STANDARD
    assert psi.entropy >= 0
    print("OK superposition")


def test_measure_deterministic_collapse():
    psi = build_superposition(
        [PATH_STANDARD, PATH_CLEANSING],
        {PATH_STANDARD: 2.0, PATH_CLEANSING: 0.5},
        context_entropy=0.1,
    )
    chosen, collapsed = measure(psi, deterministic=True)
    assert chosen == PATH_STANDARD
    assert collapsed.entropy == 0.0
    assert collapsed.amplitudes[0].probability == 1.0
    print("OK measure collapse confidence=1")


def test_reinforce_success_boosts_chosen():
    mm = {PATH_STANDARD: 1.0, PATH_CLEANSING: 1.0}
    after = reinforce(mm, PATH_STANDARD, quality=0.95)
    assert after[PATH_STANDARD] > mm[PATH_STANDARD]
    assert after[PATH_CLEANSING] < mm[PATH_CLEANSING]
    print("OK reinforce success")


def test_reinforce_failure_penalizes():
    mm = {PATH_STANDARD: 2.0, PATH_CLEANSING: 1.0}
    after = reinforce(mm, PATH_STANDARD, quality=0.5)
    assert after[PATH_STANDARD] < mm[PATH_STANDARD]
    assert after[PATH_CLEANSING] > mm[PATH_CLEANSING]
    print("OK reinforce failure")


def test_entanglement():
    s = entanglement_score(0.9, 0.9)
    assert 0.89 < s <= 1.0
    s2 = entanglement_score(0.5, 0.5, contract_match=0.5)
    assert s2 < s
    print("OK entanglement", round(s, 4))


def test_router_learning_loop():
    r = QuantumRouter(paths=(PATH_STANDARD, PATH_CLEANSING), deterministic=True)
    mm = {PATH_STANDARD: 1.2, PATH_CLEANSING: 1.0}
    for i in range(5):
        rec = r.collapse(
            charter_id="c1",
            agent_name="W1",
            muscle_memory=mm,
            marker="superstep",
            context_entropy=0.2,
        )
        q = 0.95 if rec.chosen_path == PATH_STANDARD else 0.7
        mm = r.observe("W1", mm, q)
    assert mm[PATH_STANDARD] > mm[PATH_CLEANSING]
    summary = r.summary()
    assert summary["collapses"] == 5
    print("OK router learning", mm, summary["paths"])


def test_quantum_path_select_api():
    out = quantum_path_select(
        [PATH_STANDARD, PATH_CLEANSING],
        {PATH_STANDARD: 4.0, PATH_CLEANSING: 0.5},
        deterministic=True,
        context_entropy=0.1,
    )
    assert out["chosen_path"] == PATH_STANDARD
    assert out["post_measurement"]["confidence"] == 1.0
    print("OK quantum_path_select")


def test_contextual_entropy_api():
    h = contextual_entropy({"noise": 0.9, "missing_ratio": 0.8, "variance": 0.7})
    assert h > 0.7
    print("OK contextual_entropy", round(h, 3))


def test_system_integration():
    from flowchartcharter import FlowChartCharterSystem

    sys_ = FlowChartCharterSystem(seed=7)
    result = sys_.execute_charter("Quantum Integration Job")
    assert "quantum_paths" in result
    assert "quantum_summary" in result
    assert "context_entropy" in result
    assert "Q_s_mean" in result
    assert result["quantum_summary"]["collapses"] >= 3
    print(
        "OK system integration collapses=",
        result["quantum_summary"]["collapses"],
        "H_ctx=",
        result["context_entropy"],
        "trust=",
        result["trust"],
    )


if __name__ == "__main__":
    test_superposition_normalized()
    test_measure_deterministic_collapse()
    test_reinforce_success_boosts_chosen()
    test_reinforce_failure_penalizes()
    test_entanglement()
    test_router_learning_loop()
    test_quantum_path_select_api()
    test_contextual_entropy_api()
    test_system_integration()
    print("ALL_QUANTUM_TESTS_PASSED")
