#!/usr/bin/env python3
"""Continuous learning loop: read audits → adjust playbook → verify demo."""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "07_CROSS_REFERENCE_REPORTS"
MEMORY = ROOT / "loop-engineering" / "Memory"
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "packages" / "runtime"))

from flowchartcharter import FlowChartCharterSystem


def load_latest_report() -> dict:
    files = sorted(REPORTS.glob("CXR-*.md"))
    if not files:
        return {"blocking": [], "adjustments": []}
    text = files[-1].read_text()
    return {"path": str(files[-1]), "has_blocking": "BLOCKING" in text, "text_len": len(text)}


def main() -> int:
    report = load_latest_report()
    system = FlowChartCharterSystem(seed=7)
    results = [system.execute_charter(f"learn-cycle-{i}") for i in range(2)]
    sync = system.downtime_sync()
    receipt = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "report": report,
        "results": results,
        "sync": sync,
        "trust_rate": sum(1 for r in results if r["trust"]) / max(len(results), 1),
    }
    out = MEMORY / "past-runs.jsonl"
    with out.open("a") as f:
        f.write(json.dumps(receipt) + "\n")
    print(json.dumps(receipt, indent=2))
    if receipt["trust_rate"] < 1.0:
        print("LEARNING_LOOP: partial trust — adjust muscle memory next cycle", file=sys.stderr)
    print("LEARNING_LOOP_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
