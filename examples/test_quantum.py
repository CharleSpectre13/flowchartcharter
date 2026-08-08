#!/usr/bin/env python3
"""Unit tests for quantum routing — superposition, collapse, reinforce, entanglement."""
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
)


def test_superposition_normalized():
    psi = build_superposition(["path_A", "path_B"], {"path_A": 3.0, "path_B": 1.0})
    probs = [a.probability for a in psi.amplitudes]
    assert abs(sum(probs) - 1.0) < 1e-9
    assert psi.dominant().path == "path_A"
    assert psi.amplitudes[0].probability == 0.75
    assert psi.entropy > 0  # not pure
    print("OK superposition")


def test_measure_deterministic_collapse():
    psi = build_superposition(["path_A", "path_B"], {"path_A": 2.0, "path_B": 0.5})
    chosen, collapsed = measure(psi, deterministic=True)
    assert chosen == "path_A"
    assert collapsed.entropy == 0.0
    assert collapsed.amplitudes[0].probability == 1.0
    print("OK measure collapse confidence=1")


def test_reinforce_success_boosts_chosen():
    mm = {"path_A": 1.0, "path_B": 1.0}
    after = reinforce(mm, "path_A", quality=0.95)
    assert after["path_A"] > mm["path_A"]
    assert after["path_B"] < mm["path_B"]
    print("OK reinforce success")


def test_reinforce_failure_penalizes():
    mm = {"path_A": 2.0, "path_B": 1.0}
    after = reinforce(mm, "path_A", quality=0.5)
    assert after["path_A"] < mm["path_A"]
    assert after["path_B"] > mm["path_B"]
    print("OK reinforce failure")


def test_entanglement():
    s = entanglement_score(0.9, 0.9)
    assert 0.89 < s <= 1.0
    s2 = entanglement_score(0.5, 0.5, contract_match=0.5)
    assert s2 < s
    print("OK entanglement", round(s, 4))


def test_router_learning_loop():
    r = QuantumRouter(deterministic=True)
    mm = {"path_A": 1.2, "path_B": 1.0}
    for i in range(5):
        rec = r.collapse(charter_id="c1", agent_name="W1", muscle_memory=mm, marker="superstep")
        q = 0.95 if rec.chosen_path == "path_A" else 0.7
        mm = r.observe("W1", mm, q)
    assert mm["path_A"] > mm["path_B"]
    summary = r.summary()
    assert summary["collapses"] == 5
    assert summary["mean_pre_entropy"] >= 0
    print("OK router learning", mm, summary["paths"])


def test_quantum_path_select_api():
    out = quantum_path_select(
        ["path_A", "path_B"],
        {"path_A": 4.0, "path_B": 0.5},
        deterministic=True,
    )
    assert out["chosen_path"] == "path_A"
    assert out["post_measurement"]["confidence"] == 1.0
    assert out["pre_measurement"]["entropy"] >= 0
    print("OK quantum_path_select")


def test_system_integration():
    from flowchartcharter import FlowChartCharterSystem

    sys_ = FlowChartCharterSystem(seed=7)
    result = sys_.execute_charter("Quantum Integration Job")
    assert "quantum_paths" in result
    assert "quantum_summary" in result
    assert "entanglement" in result
    assert result["quantum_summary"]["collapses"] >= 3
    # Muscle memory should have evolved
    w1 = next(a for a in sys_.roster if a.name == "Worker-1")
    assert sum(w1.muscle_memory_weights.values()) > 0
    print(
        "OK system integration collapses=",
        result["quantum_summary"]["collapses"],
        "entanglement=",
        result["entanglement"],
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
    test_system_integration()
    print("ALL_QUANTUM_TESTS_PASSED")
