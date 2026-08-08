#!/usr/bin/env python3
"""Fear-Based Accountability & Survival Mechanism tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.agents import Agent, BossAgent, AgentStatus  # noqa: E402
from flowchartcharter.survival import (  # noqa: E402
    SurvivalStatus,
    generation_params_for_risk,
    lean_rehire_check,
)
from flowchartcharter import FlowChartCharterSystem  # noqa: E402


def test_prompt_contains_survival_state() -> None:
    a = Agent("W1", "Worker")
    assert "survival_status = ACTIVE" in a.system_prompt
    assert "termination_risk_index =" in a.system_prompt
    print("OK prompt survival state")


def test_risk_spikes_on_schema_errors() -> None:
    a = Agent("W2", "Worker")
    for _ in range(3):
        a.record_cycle(
            schema_divergence=1,
            token_spend=500,
            token_ceiling=200,
            delta_t=3.0,
            structural_drift=0.5,
            quality=0.5,
            path="path_B",
        )
    assert a.termination_risk_index > 0.5
    assert a.generation.schema_lock is True
    assert a.generation.temperature < 0.5
    assert "SURVIVAL PRESSURE" in a.system_prompt
    print("OK risk spike", round(a.termination_risk_index, 3), a.generation)


def test_generation_params_monotonic() -> None:
    low = generation_params_for_risk(0.0)
    high = generation_params_for_risk(0.9)
    assert low.temperature > high.temperature
    assert low.max_tokens > high.max_tokens
    assert high.schema_lock is True
    assert high.creativity_cap < low.creativity_cap
    print("OK generation params monotonic")


def test_monday_fire_and_lean_rehire() -> None:
    boss = BossAgent("GM")
    good = Agent("Good", "Key Player - Extract", {"general": 1.0})
    bad = Agent("Bad", "Key Player - Gen", {"general": 1.0})
    for _ in range(5):
        good.execute_flow_unit(
            "ok",
            path="path_A",
            quality_bias=0.2,
            token_ceiling=500,
            expected_schema_ok=True,
        )
    for _ in range(6):
        bad.record_cycle(
            schema_divergence=1,
            token_spend=900,
            token_ceiling=200,
            delta_t=4.0,
            structural_drift=0.6,
            quality=0.4,
        )
        bad.execute_flow_unit(
            "sloppy",
            path="path_B",
            quality_bias=-0.4,
            token_ceiling=100,
            expected_schema_ok=False,
        )

    outcomes = boss.monday_morning_sync(
        [good, bad],
        muscle_memory_records=3,
        lean_rehire=True,
    )
    assert outcomes.get("Bad") == "FIRED"
    assert bad.status == AgentStatus.FIRED
    assert bad.survival_status == SurvivalStatus.TERMINATED
    assert any(not d.backfill for d in boss.rehire_log)
    print("OK fire + lean rehire", outcomes, boss.rehire_export())


def test_lean_rehire_logic() -> None:
    d1 = lean_rehire_check(
        agent_name="X", surviving_ops=2, muscle_memory_records=5
    )
    assert d1.backfill is False
    d2 = lean_rehire_check(
        agent_name="Y", surviving_ops=0, muscle_memory_records=0
    )
    assert d2.backfill is True
    print("OK lean rehire decision")


def test_system_survival_integration() -> None:
    system = FlowChartCharterSystem(seed=7)
    r = system.execute_charter("Legacy Code Refactor")
    assert "survival" in r
    assert len(r["survival"]) >= 1
    for snap in r["survival"]:
        assert "termination_risk_index" in snap
        assert "generation" in snap
    sync = system.downtime_sync()
    assert "lean_rehire" in sync
    assert "survival_board" in sync
    print(
        "OK system survival",
        "ops_after=",
        sync["active_ops_after_prune"],
        "risks=",
        [s["termination_risk_index"] for s in r["survival"]],
    )


if __name__ == "__main__":
    test_prompt_contains_survival_state()
    test_risk_spikes_on_schema_errors()
    test_generation_params_monotonic()
    test_lean_rehire_logic()
    test_monday_fire_and_lean_rehire()
    test_system_survival_integration()
    print("ALL_SURVIVAL_TESTS_PASSED")
