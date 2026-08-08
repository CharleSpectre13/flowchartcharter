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
)
from flowchartcharter_runtime import SuperStepEngine


def main() -> int:
    system = FlowChartCharterSystem(seed=42)

    kg = system.knowledge
    local = kg.local_search("charter", hops=2)
    assert len(local["nodes"]) >= 3
    glob = kg.global_search("math")
    assert glob["communities"]
    print("KG_LOCAL_NODES", len(local["nodes"]), "GLOBAL", len(glob["communities"]))

    foundations = foundations_table()
    assert len(foundations) == 6
    print("FOUNDATIONS", [f["name"] for f in foundations])

    q = quantum_path_select(["path_A", "path_B"], {"path_A": 2.0, "path_B": 0.5}, deterministic=True)
    assert q["post_measurement"]["confidence"] == 1.0
    print("QUANTUM", q["chosen_path"], "entropy_pre", q["pre_measurement"]["entropy"])

    # Learning: successive successes shift amplitudes
    router = QuantumRouter(deterministic=True)
    mm = {"path_A": 1.0, "path_B": 1.0}
    for _ in range(4):
        rec = router.collapse(charter_id="learn", agent_name="T", muscle_memory=mm)
        mm = router.observe("T", mm, 0.96)
    assert mm["path_A"] > 1.0
    print("LEARNING path_A weight", round(mm["path_A"], 3))

    assert not validate_executive_payload({"type": "chat", "msg": "hello board"})
    assert validate_executive_payload(StrategyVector(charter_id="x").to_dict())

    for job in ("Enterprise Data Migration", "API Integration Synthesis", "Security Audit Routing"):
        result = system.execute_charter(job)
        print(
            f"CHARTER {job}: quality={result['quality']:.3f} trust={result['trust']} "
            f"loops={result['remediation_loops']} collapses={result['quantum_summary']['collapses']} "
            f"Q_ent={result['entanglement']}"
        )
        assert result["quantum_summary"]["collapses"] >= 3
        assert "quantum_paths" in result
        assert result["governance"]["type"] == "GovernanceVector"

    sync = system.downtime_sync()
    print("SYNC outcomes", sync["outcomes"])
    print("MUSCLE", sync["muscle_memory"])
    assert "StrategyVector" in {g["type"] for g in sync["guidance"]}

    fired = sum(1 for v in sync["outcomes"].values() if v == "FIRED")
    assert fired <= 1

    ont_path = ROOT / "docs" / "ontology.json"
    ont_path.parent.mkdir(parents=True, exist_ok=True)
    ont_path.write_text(json.dumps(system.ontology_export(), indent=2))

    engine = SuperStepEngine()
    state = engine.run({"items": []}, [lambda s: {"items": [1]}, lambda s: {"items": [2]}])
    assert state["items"] == [1, 2]
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
