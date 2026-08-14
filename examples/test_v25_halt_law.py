#!/usr/bin/env python3
"""v2.5 Halt Law — bypass vectors closed. Independent of wrapper use."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["FCC_HARNESS_PERSIST"] = "0"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    ActionUnit_GitHubPR,
    FlowChartCharterSystem,
    HarnessKernel,
    __version__,
)
from flowchartcharter.agents import WorkerNode  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from flowchartcharter.playbook_compiler import (  # noqa: E402
    CompiledFlowUnit,
    execute_playbook_action_unit,
)

GOOD_PR = {
    "owner": "acme-corp",
    "repo": "secops-service",
    "title": "halt-law",
    "body": "bypass probe",
    "head": "fcc/halt",
    "base": "main",
    "diff": "--- a/x\n+++ b/x\n",
    "draft": True,
}


def test_version() -> None:
    assert __version__[0] in "123", __version__
    print("OK version", __version__)


def test_v1_direct_execute_halted() -> None:
    """Bypass: construct ActionUnit and skip ToolPort."""
    k = HarnessKernel()
    k.halt("direct_probe")
    unit = ActionUnit_GitHubPR(dry_run=True)
    worker = WorkerNode("H1", "Release_Operator", {"github_pr": 1.0})
    result = unit.execute(GOOD_PR, agent=worker)
    assert result.blocked is True
    assert result.error == "kill_switch_halted"
    assert result.quality == 0.0
    k.arm()
    print("OK V1 direct execute halted")


def test_v2_charter_halted() -> None:
    sys_ = FlowChartCharterSystem(seed=25)
    sys_.harness.halt("charter_probe")
    snap = sys_.execute_charter("halt law charter")
    assert snap.get("halted") is True
    assert snap.get("quality") == 0.0
    assert snap.get("trust") is False
    sys_.harness.arm()
    print("OK V2 charter refuses")


def test_v3_playbook_action_halted() -> None:
    sys_ = FlowChartCharterSystem(seed=26)
    sys_.harness.halt("playbook_probe")
    worker = WorkerNode("H3", "Release_Operator", {"github_pr": 1.0})
    unit = CompiledFlowUnit(
        id="U_PR",
        description="open pr",
        assigned_role="Release_Operator",
        expected_tokens=10,
        expected_latency_ms=1.0,
        schema_raw={},
        pydantic_model=BaseModel,
        order=1,
        unit_kind="action",
        action_type="ActionUnit_GitHubPR",
        action_config={"payload": GOOD_PR},
    )
    out = execute_playbook_action_unit(
        worker, unit, workload="halt playbook", system=sys_
    )
    assert out.get("ok") is False
    assert out.get("halted") is True
    sys_.harness.arm()
    print("OK V3 playbook action halted")


def test_v4_persist_survives() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="fcc-halt-"))
    os.environ["FCC_HARNESS_DIR"] = str(tmp)
    os.environ["FCC_HARNESS_PERSIST"] = "1"
    k = HarnessKernel(persist=True)
    k.halt("disk_probe")
    assert (tmp / "halt.json").is_file()
    k2 = HarnessKernel(persist=True)
    assert k2.kill.armed is False
    assert "disk_probe" in (k2.kill.reason or "")
    k2.arm()
    os.environ["FCC_HARNESS_PERSIST"] = "0"
    print("OK V4 persist restore")


def test_v5_playpen_overrides_live_flag() -> None:
    k = HarnessKernel()
    unit = ActionUnit_GitHubPR(dry_run=False)
    worker = WorkerNode("H5", "Release_Operator", {"github_pr": 1.0})
    result = unit.execute(GOOD_PR, agent=worker, config={"dry_run": False})
    assert result.dry_run is True
    assert result.blocked is False
    assert result.quality == 0.90
    print("OK V5 playpen forces dry-run", result.quality)


def test_v6_notebook_disk() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="fcc-nb-"))
    os.environ["FCC_HARNESS_DIR"] = str(tmp)
    os.environ["FCC_HARNESS_PERSIST"] = "1"
    k = HarnessKernel(persist=True)
    worker = WorkerNode("H6", "Release_Operator", {"github_pr": 1.0})
    k.run_action("ActionUnit_GitHubPR", worker, GOOD_PR, unit_id="U_NB")
    assert (tmp / "notebook.jsonl").is_file()
    k2 = HarnessKernel(persist=True)
    assert len(k2.notebook.records) >= 1
    os.environ["FCC_HARNESS_PERSIST"] = "0"
    print("OK V6 notebook disk", len(k2.notebook.records))


def test_v7_earned_quality() -> None:
    k = HarnessKernel()
    worker = WorkerNode("H7", "Release_Operator", {"github_pr": 1.0})
    out = k.run_action("ActionUnit_GitHubPR", worker, GOOD_PR, unit_id="U_Q")
    rhythm = out.get("rhythm_audit") or {}
    assert rhythm.get("quality") == 0.90
    assert rhythm.get("passed") is True
    print("OK V7 earned quality 0.90")


def test_v8_retrieval_stamp() -> None:
    sys_ = FlowChartCharterSystem(seed=28)
    snap = sys_.execute_charter(
        "what is FlowChartCharter",
        payload={"query": "what is FlowChartCharter", "mode": "simple"},
    )
    hit = snap.get("retrieval") or {}
    assert hit.get("claimed_graphrag") is False
    assert hit.get("backend")
    print("OK V8 retrieval stamp", hit.get("backend"))


def main() -> None:
    test_version()
    test_v1_direct_execute_halted()
    test_v2_charter_halted()
    test_v3_playbook_action_halted()
    test_v4_persist_survives()
    test_v5_playpen_overrides_live_flag()
    test_v6_notebook_disk()
    test_v7_earned_quality()
    test_v8_retrieval_stamp()
    print("ALL v2.5 HALT LAW TESTS PASSED")


if __name__ == "__main__":
    main()
