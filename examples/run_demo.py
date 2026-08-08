#!/usr/bin/env python3
import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "packages" / "runtime"))

from flowchartcharter import (
    FlowChartCharterSystem,
    validate_executive_payload,
    StrategyVector,
    foundations_table,
    quantum_path_select,
    QuantumRouter,
    synergy_score,
    contextual_entropy,
    BOSS_AGENT_SYSTEM_PROMPT,
)
from flowchartcharter_runtime import SuperStepEngine


def main() -> int:
    system = FlowChartCharterSystem(seed=42)
    assert "Coach Trust Hand-Off" in system.boss.system_prompt
    print("BOSS_ACK", system.boss_ack)
    print("SKILLS", [s["name"] for s in system.skill_catalog()])

    kg = system.knowledge
    local = kg.local_search("charter", hops=2)
    assert len(local["nodes"]) >= 3
    print("KG_LOCAL_NODES", len(local["nodes"]))

    foundations = foundations_table()
    assert len(foundations) == 6
    print("FOUNDATIONS", [f["name"] for f in foundations])

    h = contextual_entropy({"noise": 0.8, "missing_ratio": 0.6, "variance": 0.5})
    q = quantum_path_select(
        list(system.PATHS),
        {"path_A": 1.0, "path_B": 1.0, "path_lite": 1.0},
        deterministic=True,
        context_entropy=h,
    )
    print("QUANTUM H_ctx", round(h, 3), "→", q["chosen_path"], "cfo", q.get("cfo_forced"))

    qs, d = synergy_score({"x": 1, "y": "a"}, {"x": 0, "y": "b"})
    print("Q_s", qs, "D", d)

    assert not validate_executive_payload({"type": "chat", "msg": "hello board"})
    assert validate_executive_payload(StrategyVector(charter_id="x").to_dict())

    for job in ("Enterprise Data Migration", "API Integration Synthesis", "Security Audit Routing"):
        result = system.execute_charter(job)
        print(
            f"CHARTER {job}: Q={result['quality']:.3f} H_ctx={result['context_entropy']:.3f} "
            f"Q_s={result['Q_s_mean']:.3f} trust={result['trust']} "
            f"collapses={result['quantum_summary']['collapses']} Q_ent={result['entanglement']}"
        )
        assert result["quantum_summary"]["collapses"] >= 3
        assert result["boss_prompt_loaded"]

    sync = system.downtime_sync()
    print("SYNC outcomes", sync["outcomes"])
    print("MUSCLE", sync["muscle_memory"])
    assert "StrategyVector" in {g["type"] for g in sync["guidance"]}
    assert len(sync["tool_schemas"]) == 5

    ont_path = ROOT / "docs" / "ontology.json"
    ont_path.parent.mkdir(parents=True, exist_ok=True)
    ont_path.write_text(json.dumps(system.ontology_export(), indent=2))

    # Write blueprint skill catalog
    skills_path = ROOT / "docs" / "agent_skills.json"
    skills_path.write_text(json.dumps(system.skill_catalog(), indent=2))
    prompt_path = ROOT / "docs" / "boss_system_prompt.txt"
    prompt_path.write_text(BOSS_AGENT_SYSTEM_PROMPT)

    engine = SuperStepEngine()
    state = engine.run({"items": []}, [lambda s: {"items": [1]}, lambda s: {"items": [2]}])
    assert state["items"] == [1, 2]
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
