#!/usr/bin/env python3
"""continuous-team-audit-loop — live harness probe. Maker ≠ checker."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("FCC_HARNESS_PERSIST", "0")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    FlowChartCharterSystem,
    format_audit_report,
    run_system_audit,
)

REPORTS = ROOT / "07_CROSS_REFERENCE_REPORTS"


def main() -> int:
    system = FlowChartCharterSystem(seed=32)
    receipt = run_system_audit(system)
    body = format_audit_report(receipt)
    REPORTS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = REPORTS / f"CXR-{ts}-live-audit.md"
    path.write_text(body + "\n", encoding="utf-8")
    print(body)
    print("wrote", path)
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
