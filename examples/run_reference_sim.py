#!/usr/bin/env python3
"""Run the FlowChartCharter Architectural Reference simulation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.reference_engine import (  # noqa: E402
    CFOHaltError,
    ReferenceQuantumRouter,
    TypedFlowUnit,
    run_reference_simulation,
)


def main() -> int:
    print("=" * 60)
    print("FLOWCHARTCHARTER REFERENCE SIMULATION")
    print("=" * 60)

    result = run_reference_simulation(quiet=False)

    print("\n--- Collapse detail ---")
    print(json.dumps(result["collapse"], indent=2))

    print("\n--- High H_ctx path (messy data) ---")
    print(result["messy_path"])

    print("\n--- Roster after sync ---")
    print(result["roster_status"])

    # CFO halt path
    router = ReferenceQuantumRouter()
    expensive = [
        TypedFlowUnit("X1", "Huge RAG", 0.5, 50_000, handles_uncertainty=0.9),
    ]
    try:
        router.collapse_wave_function(0.5, expensive, cfo_budget=100)
        print("ERROR: expected CFOHaltError")
        return 1
    except CFOHaltError as exc:
        print(f"\nCFO Halt verified: {exc}")

    # Assert reference invariants (match architectural paste)
    assert result["chosen_path"]["id"] == "U1", "clear data + budget → U1"
    assert result["roster_status"]["A2"] == "FIRED", "costly agent must fire"
    assert result["roster_status"]["A3"] == "PROMOTED", "perfect QA must promote"
    assert result["messy_path"]["id"] == "U3", "messy data → cleansing unit"

    # Integrate with full system facade
    from flowchartcharter import FlowChartCharterSystem  # noqa: E402

    system = FlowChartCharterSystem(seed=42)
    charter = system.execute_charter("Reference Integration Job")
    print(
        f"\nFull system charter: Q={charter['quality']:.3f} "
        f"H_ctx={charter['context_entropy']:.3f} trust={charter['trust']}"
    )
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
