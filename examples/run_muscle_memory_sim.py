#!/usr/bin/env python3
"""Muscle-Memory Vector DB simulation (architectural reference)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.muscle_memory import (  # noqa: E402
    MuscleMemoryVectorDB,
    seed_legacy_refactor,
)


def main() -> int:
    print("=" * 60)
    print("MUSCLE-MEMORY VECTOR DB SIMULATION")
    print("=" * 60)

    db = MuscleMemoryVectorDB(quiet=False)
    seed_legacy_refactor(db)

    incoming = {
        "task": "Legacy Code Refactor",
        "codebase_snippet": "function test() { var x = 1; }",
        "metadata": {"source": "legacy_repo"},
    }

    print("\n[Workload Received] Agent checking Muscle-Memory...")
    matched = db.query_muscle_memory(
        incoming,
        similarity_threshold=0.70,
        state_vector=[0.45, 12.5, 4.0, 0.1],
    )

    if matched:
        print(
            f"Execution Accelerated! Reusing Flow Path: "
            f"{matched.successful_flow_path}"
        )
        print(f"Applied Cheat Code: '{matched.prompt_tweak}'")
        print(f"Q_entanglement fingerprint: {matched.entanglement_score}")
    else:
        print("Executing default standard charter path.")
        return 1

    encoded = db.encode_state(incoming)
    print(f"\nEncoded state vector: {[round(x, 4) for x in encoded]}")

    from flowchartcharter import FlowChartCharterSystem  # noqa: E402

    system = FlowChartCharterSystem(seed=1)
    result = system.execute_charter("Legacy Code Refactor", payload=incoming)
    print(
        f"\nSystem charter: Q={result['quality']:.3f} "
        f"MM_hit={result['muscle_memory_hit']} "
        f"path={result.get('flow_path_reused')}"
    )
    print("DB stats:", json.dumps(system.muscle_db.stats()))
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
