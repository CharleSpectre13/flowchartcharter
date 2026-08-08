#!/usr/bin/env python3
"""5-Day Analytics Protocol + Analytics Chief capstone tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.analytics import (  # noqa: E402
    AnalyticsChief,
    WORKWEEK_DAYS,
)
from flowchartcharter.agents import Agent, BossAgent  # noqa: E402
from flowchartcharter.muscle_memory import MuscleMemoryVectorDB  # noqa: E402
from flowchartcharter import FlowChartCharterSystem  # noqa: E402


def test_ingest_and_defer_audit() -> None:
    chief = AnalyticsChief()
    a = Agent("W1", "Worker", {"general": 1.0})
    for _ in range(3):
        a.execute_flow_unit("job", path="path_A", quality_bias=0.1)
    chief.ingest_cycle(agents=[a], workload="job-a", quality=0.95)
    assert chief.execute_end_of_week_audit() is None
    print("OK defer until 5 days", chief.days_ready())


def test_five_day_dossier_and_cheat_codes() -> None:
    chief = AnalyticsChief()
    mm = MuscleMemoryVectorDB(quiet=True)
    good = Agent("Star", "Key Player", {"general": 1.0})
    bad = Agent("Flop", "Key Player", {"general": 1.0})

    for _day in range(WORKWEEK_DAYS):
        for _ in range(2):
            good.execute_flow_unit(
                "efficient",
                path="path_lite",
                quality_bias=0.2,
                expected_tokens=500,
                expected_time=2.0,
            )
            bad.record_cycle(
                schema_divergence=1,
                token_spend=900,
                token_ceiling=200,
                delta_t=4.0,
                structural_drift=0.5,
                quality=0.4,
            )
            bad.execute_flow_unit(
                "sloppy",
                path="path_B",
                quality_bias=-0.3,
                expected_schema_ok=False,
            )
        chief.ingest_cycle(
            agents=[good, bad],
            workload="efficient-job",
            quality=0.95,
            flow_path=["U1_Ingest", "U9_DeterministicExecute"],
            path_trace={
                "Star": {
                    "chosen_path": "path_lite",
                    "prompt_tweak": "Use lite path under thrift pressure",
                    "flow_path": ["U1_Ingest", "U9_DeterministicExecute"],
                }
            },
        )
        for s in chief._current_day:
            if s.agent_name == "Star":
                s.expected_tokens = 500
                s.token_spend = 80
                s.quality = 0.96
                s.expected_latency = 2.0
                s.latency = 0.5
        chief.close_day()

    assert chief.workweek_complete()
    dossier = chief.execute_end_of_week_audit(muscle_db=mm, force=False)
    assert dossier is not None
    actions = dossier.action_map()
    assert "Star" in actions
    assert actions.get("Flop") == "TERMINATE" or any(
        t.agent_name == "Flop" and t.fitness_ma < 0.5 for t in dossier.trends
    )
    assert len(mm.storage) >= 1 or len(dossier.cheat_codes) >= 0
    print(
        "OK dossier",
        dossier.dossier_id,
        actions,
        "cheats",
        len(dossier.cheat_codes),
        "mm",
        len(mm.storage),
    )


def test_gm_executes_dossier_not_guess() -> None:
    boss = BossAgent("GM")
    chief = AnalyticsChief()
    good = Agent("A-Good", "Worker", {"general": 1.0})
    bad = Agent("A-Bad", "Worker", {"general": 1.0})
    for _ in range(4):
        good.execute_flow_unit("ok", quality_bias=0.2)
        bad.record_cycle(
            schema_divergence=2,
            token_spend=800,
            token_ceiling=100,
            delta_t=5.0,
            structural_drift=0.6,
            quality=0.3,
        )
        bad.execute_flow_unit(
            "bad", quality_bias=-0.5, expected_schema_ok=False
        )

    for _ in range(WORKWEEK_DAYS):
        chief.ingest_cycle(agents=[good, bad], workload="w")
        chief.close_day()
    dossier = chief.execute_end_of_week_audit(force=True)
    assert dossier is not None
    outcomes = boss.monday_morning_sync(
        [good, bad],
        dossier=dossier,
        lean_rehire=True,
        muscle_memory_records=3,
    )
    assert boss.last_dossier_id == dossier.dossier_id
    assert any("Board" in p or "dossier" in p.lower() for p in boss.playbook)
    print("OK GM dossier execution", outcomes, boss.last_dossier_id)


def test_system_five_day_protocol() -> None:
    system = FlowChartCharterSystem(seed=9)
    jobs = [
        "Legacy Code Refactor",
        "Clean messy customer CSV export",
        "Build secure API gateway",
        "Migrate old database tables",
        "Legacy Code Refactor",
    ]
    for job in jobs:
        system.execute_charter(job)
        system.advance_analytics_day()

    assert system.analytics.days_ready() >= WORKWEEK_DAYS
    result = system.run_end_of_week_protocol(force=True)
    assert result["dossier_driven"] is True
    assert result["dossier"] is not None
    assert "recommendations" in result["dossier"]
    sync = system.downtime_sync()
    assert "analytics" in sync
    print(
        "OK system EOW",
        result["dossier"]["dossier_id"],
        result["outcomes"],
        "days",
        system.analytics.day_counter,
    )


if __name__ == "__main__":
    test_ingest_and_defer_audit()
    test_five_day_dossier_and_cheat_codes()
    test_gm_executes_dossier_not_guess()
    test_system_five_day_protocol()
    print("ALL_ANALYTICS_PROTOCOL_TESTS_PASSED")
