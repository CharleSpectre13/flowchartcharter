#!/usr/bin/env python3
"""v3.2 Live system audit tool on the harness."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["FCC_HARNESS_PERSIST"] = "0"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    FlowChartCharterSystem,
    __version__,
    format_audit_report,
    run_system_audit,
)


def test_version() -> None:
    assert __version__.startswith("3."), __version__
    print("OK version", __version__)


def test_v1_all_probes() -> None:
    sys_ = FlowChartCharterSystem(seed=32)
    receipt = run_system_audit(sys_)
    assert receipt["ok"] is True, receipt.get("failed")
    names = {p["name"] for p in receipt["probes"]}
    for need in (
        "halt_roundtrip",
        "simple_muscle",
        "retrieval_honesty",
        "citation_law",
        "episode_bind",
        "qfs_reduce",
        "rhythm_independent",
    ):
        assert need in names
    print("OK V1 probes", sorted(names))


def test_v2_harness_toolbox() -> None:
    sys_ = FlowChartCharterSystem(seed=32)
    receipt = sys_.audit_live()
    assert receipt["ok"] is True
    assert sys_.harness.notebook.records
    print("OK V2 harness.audit")


def test_v3_report_and_honesty() -> None:
    sys_ = FlowChartCharterSystem(seed=32)
    receipt = run_system_audit(sys_)
    text = format_audit_report(receipt)
    assert "PASS" in text
    assert receipt.get("claimed_graphrag") is False
    print("OK V3 report")


def main() -> None:
    test_version()
    test_v1_all_probes()
    test_v2_harness_toolbox()
    test_v3_report_and_honesty()
    print("ALL v3.2 SYSTEM AUDIT TESTS PASSED")


if __name__ == "__main__":
    main()
