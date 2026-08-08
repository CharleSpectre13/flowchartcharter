#!/usr/bin/env python3
"""Tests for Muscle-Memory Vector DB (architectural reference)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.muscle_memory import (  # noqa: E402
    ExecutionMemoryRecord,
    MuscleMemoryVectorDB,
    encode_state,
    cosine_similarity,
    run_muscle_memory_simulation,
    seed_legacy_refactor,
)
from flowchartcharter import FlowChartCharterSystem  # noqa: E402


def test_encode_state() -> None:
    vec = encode_state({"a": 1, "b": "x"})
    assert len(vec) == 4
    assert vec[2] == 2.0  # two keys
    print("OK encode_state", [round(x, 4) for x in vec])


def test_cosine() -> None:
    assert abs(cosine_similarity([1, 0], [1, 0]) - 1.0) < 1e-9
    assert cosine_similarity([1, 0], [0, 1]) < 0.01
    print("OK cosine")


def test_commit_and_query_hit() -> None:
    db = MuscleMemoryVectorDB(quiet=True)
    seed_legacy_refactor(db)
    hit = db.query_muscle_memory(
        {"task": "Legacy Code Refactor"},
        similarity_threshold=0.70,
        state_vector=[0.45, 12.5, 4.0, 0.1],
    )
    assert hit is not None
    assert hit.memory_id == "MEM-9921"
    assert hit.successful_flow_path[0] == "U1_Ingest"
    assert "camelCase" in hit.prompt_tweak
    assert db.stats()["hits"] == 1
    print("OK HIT", hit.successful_flow_path)


def test_miss_below_threshold() -> None:
    db = MuscleMemoryVectorDB(quiet=True)
    seed_legacy_refactor(db)
    miss = db.query_muscle_memory(
        {"unrelated": True},
        similarity_threshold=0.99,
        state_vector=[0.0, 0.0, 0.0, 0.0],
    )
    assert miss is None
    assert db.stats()["misses"] >= 1
    print("OK MISS fallback to charter")


def test_quality_gate_on_commit() -> None:
    db = MuscleMemoryVectorDB(quiet=True)
    bad = ExecutionMemoryRecord(
        memory_id="BAD",
        job_type="x",
        state_vector=[1, 0, 0, 0],
        successful_flow_path=["U0"],
        entanglement_score=0.5,
        quality=0.5,
    )
    db.commit_memory(bad)
    assert len(db.storage) == 0  # rejected
    print("OK quality gate rejects low-trust memory")


def test_simulation() -> None:
    result = run_muscle_memory_simulation(quiet=True)
    assert result["exact_hit"] is True
    assert result["exact_path"] == [
        "U1_Ingest",
        "U4_TypeSanitize",
        "U8_DeterministicRefactor",
    ]
    assert "camelCase" in (result["exact_tweak"] or "")
    print("OK simulation", result["stats"])


def test_system_integration() -> None:
    system = FlowChartCharterSystem(seed=3)
    # Force a hit via seeded migration vector-ish state
    r = system.execute_charter(
        "Legacy Code Refactor",
        payload={
            "task": "Legacy Code Refactor",
            "codebase_snippet": "function test() { var x = 1; }",
        },
    )
    assert "muscle_memory_hit" in r
    assert "muscle_db_stats" in r
    sync = system.downtime_sync()
    assert "muscle_db" in sync
    assert sync["muscle_db"]["stats"]["records"] >= 1
    print(
        "OK system MM hit=",
        r["muscle_memory_hit"],
        "records=",
        r["muscle_db_stats"]["records"],
    )


if __name__ == "__main__":
    test_encode_state()
    test_cosine()
    test_commit_and_query_hit()
    test_miss_below_threshold()
    test_quality_gate_on_commit()
    test_simulation()
    test_system_integration()
    print("ALL_MUSCLE_MEMORY_TESTS_PASSED")
