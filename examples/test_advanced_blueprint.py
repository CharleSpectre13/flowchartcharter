#!/usr/bin/env python3
"""Cycle 5 — Advanced System Blueprint tests (tensor routing, skills, Q_s, CFO)."""
from __future__ import annotations
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (
    FlowChartCharterSystem,
    AgentSkillRuntime,
    MuscleMemoryStore,
    MuscleMemoryRecord,
    synergy_score,
    structural_divergence,
    contextual_entropy,
    apply_cfo_budget_matrix,
    build_superposition,
    BOSS_AGENT_SYSTEM_PROMPT,
    AGENT_SKILL_SCHEMAS,
    PATH_LITE,
    PATH_CLEANSING,
    PATH_STANDARD,
)


def test_contextual_entropy():
    h_messy = contextual_entropy({"noise": 0.9, "missing_ratio": 0.8, "variance": 0.7})
    h_clean = contextual_entropy({"noise": 0.05, "missing_ratio": 0.0, "variance": 0.1})
    assert h_messy > 0.7
    assert h_clean < 0.2
    assert contextual_entropy(explicit=0.55) == 0.55
    print("OK contextual_entropy", round(h_messy, 3), round(h_clean, 3))


def test_high_entropy_prefers_cleansing():
    mm = {PATH_STANDARD: 1.0, PATH_CLEANSING: 1.0, PATH_LITE: 1.0}
    psi_messy = build_superposition(
        [PATH_STANDARD, PATH_CLEANSING, PATH_LITE],
        mm,
        context_entropy=0.95,
    )
    psi_clean = build_superposition(
        [PATH_STANDARD, PATH_CLEANSING, PATH_LITE],
        mm,
        context_entropy=0.05,
    )
    p_b_messy = next(a.probability for a in psi_messy.amplitudes if a.path == PATH_CLEANSING)
    p_b_clean = next(a.probability for a in psi_clean.amplitudes if a.path == PATH_CLEANSING)
    assert p_b_messy > p_b_clean
    print("OK H_ctx bias", round(p_b_messy, 3), ">", round(p_b_clean, 3))


def test_synergy_formula():
    qs, d = synergy_score(
        {"a": 1, "b": "x", "c": 3.0},
        {"a": 0, "b": "y", "c": 0.0},
    )
    assert d == 0.0
    assert abs(qs - 1.0) < 1e-9
    qs2, d2 = synergy_score({"a": 1}, {"a": 0, "b": "missing", "c": True})
    assert d2 > 0.5
    assert qs2 < 0.5  # exp(-3*D) decays fast
    assert abs(qs2 - math.exp(-3.0 * d2)) < 1e-9
    print("OK Q_s = exp(-kD)", round(qs2, 4), "D", round(d2, 4))


def test_cfo_forces_lite():
    weights = {PATH_STANDARD: 2.0, PATH_CLEANSING: 2.0, PATH_LITE: 1.0}
    costs = {PATH_STANDARD: 5000, PATH_CLEANSING: 8000, PATH_LITE: 90}
    adj, blocked, forced = apply_cfo_budget_matrix(
        weights, costs, remaining_budget=100, margin=50
    )
    assert forced or adj.get(PATH_LITE, 0) > 0
    assert PATH_STANDARD in blocked or adj[PATH_STANDARD] == 0
    print("OK CFO matrix force_lite", forced, "blocked", blocked)


def test_boss_prompt():
    assert "Coach Trust Hand-Off" in BOSS_AGENT_SYSTEM_PROMPT
    assert "Monday Morning Sync" in BOSS_AGENT_SYSTEM_PROMPT
    assert "Blackboard" in BOSS_AGENT_SYSTEM_PROMPT
    s = FlowChartCharterSystem(seed=0)
    assert s.boss.system_prompt == BOSS_AGENT_SYSTEM_PROMPT
    assert "Acknowledged" in s.boss_ack
    print("OK Boss prompt loaded")


def test_five_skills():
    names = {s["name"] for s in AGENT_SKILL_SCHEMAS}
    assert names == {
        "QueryMuscleMemory",
        "EvaluateRhythmMarker",
        "ExecuteQuantumCollapse",
        "TriggerMondayMorningSync",
        "AdjustCorporateRoster",
    }
    s = FlowChartCharterSystem(seed=2)
    # QueryMuscleMemory
    hits = s.skills.QueryMuscleMemory([0.8, 0.2, 0.1, 0.9], threshold=0.7)
    assert hits["hit_count"] >= 1
    # EvaluateRhythmMarker
    ev = s.skills.EvaluateRhythmMarker(
        {"result": "ok", "quality": 0.95, "path": "path_A", "tokens": 100},
        {"result": "ok", "quality": 0.9, "path": "path_A", "tokens": 100},
    )
    assert ev["passed"] is True
    assert ev["Q_s"] == 1.0
    # ExecuteQuantumCollapse
    col = s.skills.ExecuteQuantumCollapse(
        list(s.PATHS),
        context_entropy=0.8,
        muscle_memory=s.roster[0].muscle_memory_weights,
        agent_name="Worker-1",
    )
    assert col["post_measurement"]["confidence"] == 1.0
    assert col["chosen_path"] in s.PATHS
    # AdjustCorporateRoster
    aid = s.roster[0].id
    adj = s.skills.AdjustCorporateRoster(aid, "PROMOTE")
    assert adj["ok"] and adj["action"] == "PROMOTE"
    # TriggerMondayMorningSync
    sync = s.skills.TriggerMondayMorningSync(
        {"path_stats": {"path_A": {"success_rate": 0.9}}},
        roster=s.roster,
        boss=s.boss,
    )
    assert sync["skill"] == "TriggerMondayMorningSync"
    print("OK five skills")


def test_system_end_to_end():
    s = FlowChartCharterSystem(seed=42)
    r1 = s.execute_charter("Enterprise Data Migration")  # high H_ctx keyword
    assert r1["context_entropy"] > 0.5
    assert r1["Q_s_mean"] > 0.9
    assert "quantum_paths" in r1
    assert r1["precedent"]["skill"] == "QueryMuscleMemory"
    r2 = s.execute_charter("API Integration Synthesis")
    assert r2["trust"] in (True, False)
    sync = s.downtime_sync()
    assert set(sync["tool_schemas"]) == {
        "QueryMuscleMemory",
        "EvaluateRhythmMarker",
        "ExecuteQuantumCollapse",
        "TriggerMondayMorningSync",
        "AdjustCorporateRoster",
    }
    print(
        "OK e2e H_ctx",
        r1["context_entropy"],
        "collapses",
        r1["quantum_summary"]["collapses"],
        "trust",
        r1["trust"],
    )


if __name__ == "__main__":
    test_contextual_entropy()
    test_high_entropy_prefers_cleansing()
    test_synergy_formula()
    test_cfo_forces_lite()
    test_boss_prompt()
    test_five_skills()
    test_system_end_to_end()
    print("ALL_ADVANCED_BLUEPRINT_TESTS_PASSED")
