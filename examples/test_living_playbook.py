#!/usr/bin/env python3
"""Living Playbook & Automation Ascension tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.living_playbook import (  # noqa: E402
    LivingPlaybook,
    seed_living_playbook,
    objective_signature_from_payload,
    capability_map_from_path,
)
from flowchartcharter import FlowChartCharterSystem  # noqa: E402


def test_objective_signature() -> None:
    sig = objective_signature_from_payload(
        {"task": "Refactor legacy authentication module"},
        entropy=0.4,
    )
    assert len(sig) == 6
    assert all(0.0 <= x <= 1.0 for x in sig)
    print("OK objective_signature", [round(x, 3) for x in sig])


def test_capability_map() -> None:
    caps = capability_map_from_path(
        ["U1_Ingest", "U8_DeterministicRefactor", "U5_SecureTokenReplace"]
    )
    assert "python_ast" in caps or "refactoring" in caps
    assert "security_audit" in caps
    print("OK capability_map", caps)


def test_hit_on_seeded_job() -> None:
    pb = LivingPlaybook(ascension_threshold=12)
    seed_living_playbook(pb)
    result = pb.synthesize_charter(
        {"task": "Legacy Code Refactor"},
        entropy=0.4,
    )
    assert result["mode"] == "hit"
    assert result["path"] is not None
    assert "U1_Ingest" in result["path"]
    print("OK living HIT", result["memory_id"], result["path"])


def test_zero_shot_synthesis() -> None:
    pb = LivingPlaybook(ascension_threshold=5)
    seed_living_playbook(pb)
    assert pb.horizon_reached is True
    result = pb.synthesize_charter(
        {"task": "Hybrid refactor of auth gateway with CSV cleanup"},
        entropy=0.6,
        force_zero_shot=True,
    )
    assert result["mode"] == "zero_shot"
    assert result["path"] and len(result["path"]) >= 2
    assert result["ascension"] is True
    print(
        "OK zero-shot",
        result["path"],
        result.get("weights"),
        result["rationale"][:60],
    )


def test_cross_generational_remap() -> None:
    pb = LivingPlaybook(model_class="70B")
    seed_living_playbook(pb)
    before = len(pb.records)
    upgrade = pb.upgrade_generation(
        "1T",
        {
            "python_ast": 1.0,
            "refactoring": 1.0,
            "security_audit": 0.95,
            "general": 0.8,
            "json_parsing": 0.9,
        },
    )
    assert upgrade["model_class"] == "1T"
    assert upgrade["remapped_count"] == before
    assert pb.evolution_iteration >= 2
    # remapped records carry new model class
    assert any(r.origin_model_class == "1T" for r in pb.records)
    print("OK remap", upgrade["remapped_count"], pb.model_class, pb.evolution_iteration)


def test_system_living_playbook() -> None:
    system = FlowChartCharterSystem(seed=5, model_class="70B")
    r = system.execute_charter("Legacy Code Refactor")
    assert r["playbook_mode"] in ("hit", "zero_shot")
    assert r["flow_path_reused"]
    assert r["playbook_export"]["records"] >= 12
    # personnel upgrade
    up = system.upgrade_personnel("1T")
    assert up["model_class"] == "1T"
    # zero-shot novel hybrid
    r2 = system.execute_charter(
        "Hybrid secure API refactor with data cleanse",
        force_zero_shot=True,
    )
    assert r2["playbook_mode"] in ("zero_shot", "hit")
    sync = system.downtime_sync()
    assert "living_playbook" in sync
    print(
        "OK system",
        r["playbook_mode"],
        r2["playbook_mode"],
        "horizon",
        sync["ascension"],
    )


if __name__ == "__main__":
    test_objective_signature()
    test_capability_map()
    test_hit_on_seeded_job()
    test_zero_shot_synthesis()
    test_cross_generational_remap()
    test_system_living_playbook()
    print("ALL_LIVING_PLAYBOOK_TESTS_PASSED")
