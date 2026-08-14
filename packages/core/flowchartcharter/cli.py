"""CLI helpers — package entrypoints.

- fcc-audit  → audit_main (live probes)
- fcc        → flowchartcharter.fcc_cli:run
"""
from __future__ import annotations

import os


def audit_main() -> None:
    """pep8 + live system probes. Maker ≠ checker."""
    os.environ.setdefault("FCC_HARNESS_PERSIST", "0")
    try:
        from .system_audit import format_audit_report, run_system_audit
        from .system import FlowChartCharterSystem
        from .live_model import LiveModel

        receipt = run_system_audit(FlowChartCharterSystem(seed=7))
        print(format_audit_report(receipt))
        print("live_model", LiveModel.from_env().status())
        raise SystemExit(0 if receipt.get("ok") else 1)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("audit_fallback", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    audit_main()
