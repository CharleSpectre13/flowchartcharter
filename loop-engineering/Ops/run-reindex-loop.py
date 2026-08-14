#!/usr/bin/env python3
"""Delta reindex loop: extract → verify → merge. No full rebuild. No GraphRAG claim."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ROOT / "loop-engineering" / "Memory"
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import FlowChartCharterSystem, run_reindex_loop  # noqa: E402


def main() -> int:
    system = FlowChartCharterSystem(seed=27)
    docs = [
        {
            "source_id": "pilot-a",
            "text": "FlowChartCharter uses Rhythm Markers.",
        },
        {
            "source_id": "pilot-b",
            "text": (
                "DeltaNotebook stores charter receipts. "
                "DeltaNotebook depends on DurableNotebook."
            ),
        },
    ]
    report = run_reindex_loop(
        system.knowledge,
        docs,
        implementor_role="Extractor",
        auditor_role="Audit Manager",
    )
    receipt = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "loop": "reindex",
        "full_rebuild": False,
        "claimed_graphrag": False,
        **report,
    }
    out = MEMORY / "past-runs.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, default=str) + "\n")
    print(json.dumps({k: receipt[k] for k in (
        "ok", "docs", "added", "full_rebuild", "claimed_graphrag"
    )}, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
