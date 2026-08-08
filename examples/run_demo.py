#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "packages" / "runtime"))

from flowchartcharter import FlowChartCharterSystem
from flowchartcharter_runtime import SuperStepEngine, merge_snapshots


def main() -> int:
    system = FlowChartCharterSystem(seed=42)
    for job in ("Enterprise Data Migration", "API Integration Synthesis", "Security Audit Routing"):
        result = system.execute_charter(job)
        print(f"CHARTER {job}: quality={result['quality']:.3f} trust={result['trust']} loops={result['remediation_loops']}")

    outcomes = system.downtime_sync()
    print("SYNC", outcomes)

    engine = SuperStepEngine()
    state = engine.run({"items": []}, [lambda s: {"items": [1]}, lambda s: {"items": [2]}])
    assert state["items"] == [1, 2], state
    assert state["_superstep"] == 1
    print("SUPERSTEP_OK", state)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
