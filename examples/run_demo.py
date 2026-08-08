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
    KnowledgeGraph,
    foundations_table,
    quantum_path_select,
)
from flowchartcharter_runtime import SuperStepEngine


def main() -> int:
    system = FlowChartCharterSystem(seed=42)

    # KG local + global
    kg = system.knowledge
    local = kg.local_search("charter", hops=2)
    assert len(local["nodes"]) >= 3
    glob = kg.global_search("operations")
    assert glob["communities"]
    print("KG_LOCAL_NODES", len(local["nodes"]), "GLOBAL", len(glob["communities"]))

    # Foundations table from spreadsheet
    foundations = foundations_table()
    assert len(foundations) == 6
    assert foundations[0]["id"] == "charter"
    print("FOUNDATIONS", [f["name"] for f in foundations])

    # Quantum collapse deterministic
    q = quantum_path_select(["path_A", "path_B"], {"path_A": 2.0, "path_B": 0.5}, deterministic=True)
    assert q["post_measurement"]["confidence"] == 1.0
    print("QUANTUM", q["chosen_path"], "entropy_pre", q["pre_measurement"]["entropy"])

    assert not validate_executive_payload({"type": "chat", "msg": "hello board"})
    assert validate_executive_payload(StrategyVector(charter_id="x").to_dict())

    for job in ("Enterprise Data Migration", "API Integration Synthesis", "Security Audit Routing"):
        result = system.execute_charter(job)
        print(
            f"CHARTER {job}: quality={result['quality']:.3f} trust={result['trust']} "
            f"loops={result['remediation_loops']} audit={result['rhythm_audit']['passed']}"
        )
        assert "quantum_paths" in result
        assert result["governance"]["type"] == "GovernanceVector"

    sync = system.downtime_sync()
    print("SYNC outcomes", sync["outcomes"])
    print("KG_SYNTHESIS", sync["knowledge_global"]["synthesis"][:120], "...")
    assert "StrategyVector" in {g["type"] for g in sync["guidance"]}

    fired = sum(1 for v in sync["outcomes"].values() if v == "FIRED")
    assert fired <= 1, f"mass-fire: {fired}"

    # Export ontology artifact
    ont_path = ROOT / "docs" / "ontology.json"
    ont_path.parent.mkdir(parents=True, exist_ok=True)
    ont_path.write_text(json.dumps(system.ontology_export(), indent=2))
    print("ONTOLOGY_WRITTEN", ont_path, "entities", len(system.ontology_export()["entities"]))

    engine = SuperStepEngine()
    state = engine.run({"items": []}, [lambda s: {"items": [1]}, lambda s: {"items": [2]}])
    assert state["items"] == [1, 2]
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
