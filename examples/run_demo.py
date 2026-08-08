#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "packages" / "runtime"))

from flowchartcharter import (
    FlowChartCharterSystem,
    validate_executive_payload,
    StrategyVector,
)
from flowchartcharter_runtime import SuperStepEngine


def main() -> int:
    system = FlowChartCharterSystem(seed=42)

    assert not validate_executive_payload({"type": "chat", "msg": "hello board"})
    assert validate_executive_payload(StrategyVector(charter_id="x").to_dict())

    for job in ("Enterprise Data Migration", "API Integration Synthesis", "Security Audit Routing"):
        result = system.execute_charter(job)
        print(
            f"CHARTER {job}: quality={result['quality']:.3f} trust={result['trust']} "
            f"loops={result['remediation_loops']} audit={result['rhythm_audit']['passed']} "
            f"gov={result['governance']['approve_hand_off']}"
        )
        assert result["governance"]["type"] == "GovernanceVector"
        assert result["rhythm_audit"]["type"] == "RhythmAudit"

    sync = system.downtime_sync()
    print("SYNC outcomes", sync["outcomes"])
    print("GUIDANCE types", [g["type"] for g in sync["guidance"]])
    assert set(g["type"] for g in sync["guidance"]) >= {
        "StrategyVector",
        "BudgetVector",
        "GovernanceVector",
    }
    assert sync["ops"]["type"] == "OpsVector"

    fired = sum(1 for v in sync["outcomes"].values() if v == "FIRED")
    print(f"FIRED_COUNT={fired}")
    # operational workers only; validators/executives excluded from talent loop
    assert fired <= 1, f"mass-fire regression: {fired} fired"
    assert "Validator-1" not in sync["outcomes"]

    engine = SuperStepEngine()
    state = engine.run({"items": []}, [lambda s: {"items": [1]}, lambda s: {"items": [2]}])
    assert state["items"] == [1, 2], state
    print("SUPERSTEP_OK", state)
    print("VECTOR_COUNT", len(system.blackboard.executive_vectors))
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
