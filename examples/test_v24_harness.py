#!/usr/bin/env python3
"""v2.4 CharterHarness — car under the Charter. V1–V8."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    DurableNotebook,
    ExecutionSandbox,
    FlowChartCharterSystem,
    HarnessKernel,
    KillSwitch,
    ScenarioSandbox,
    SimulationSandbox,
    __version__,
)
from flowchartcharter.agents import WorkerNode  # noqa: E402


GOOD_PR = {
    "owner": "acme-corp",
    "repo": "secops-service",
    "title": "harness: dry-run patch",
    "body": "FCC harness test",
    "head": "fcc/harness",
    "base": "main",
    "diff": "--- a/x\n+++ b/x\n",
    "draft": True,
}


def test_version() -> None:
    assert __version__[0] in "123", __version__
    print("OK version", __version__)


def test_v1_halt_blocks_action() -> None:
    k = HarnessKernel()
    worker = WorkerNode("H1", "Release_Operator", {"github_pr": 1.0})
    k.halt("test_stop")
    out = k.run_action("ActionUnit_GitHubPR", worker, GOOD_PR, unit_id="U_PR")
    assert out["status"] == "HALTED", out
    assert out.get("http") is False
    assert "SUCCESS_HTTP_POST" != out["status"]
    print("OK V1 halt blocks", out["status"])


def test_v2_model_cannot_lie_done() -> None:
    k = HarnessKernel()
    claim = k.claim_done(True, required=1)
    assert claim["done"] is False
    assert claim["rejected"] is True
    assert claim["reason"] == "model_claimed_done_without_rhythm"
    print("OK V2 done rejected")


def test_v3_schema_fear() -> None:
    k = HarnessKernel()
    worker = WorkerNode("H2", "Release_Operator", {"github_pr": 1.0})
    bad = k.run_action(
        "ActionUnit_GitHubPR",
        worker,
        {"msg": "not a pr", "channel": "#wrong"},
        unit_id="U_BAD",
    )
    assert str(bad["status"]).startswith("BLOCKED"), bad
    assert bad.get("http") not in (True, "ok")
    print("OK V3 fear blocked", bad["status"])


def test_v4_notebook_record() -> None:
    k = HarnessKernel()
    worker = WorkerNode("H3", "Release_Operator", {"github_pr": 1.0})
    out = k.run_action("ActionUnit_GitHubPR", worker, GOOD_PR, unit_id="U_OK")
    rec = out.get("notebook") or {}
    assert rec.get("checkpoint_id", "").startswith("NB-"), rec
    assert rec.get("rhythm_audit"), rec
    assert k.notebook.last() is not None
    print("OK V4 notebook", rec["checkpoint_id"])


def test_v5_retrieval_honest() -> None:
    k = HarnessKernel()
    hit = k.retrieve("what is FlowChartCharter", mode="simple")
    assert hit.claimed_graphrag is False
    assert hit.backend == "muscle_memory"
    print("OK V5 retrieval", hit.backend)


def test_v6_scenario_alias() -> None:
    assert ScenarioSandbox is SimulationSandbox
    print("OK V6 ScenarioSandbox alias")


def test_v7_no_vendor_sdk() -> None:
    text = (ROOT / "pyproject.toml").read_text()
    for banned in ("openai", "anthropic", "litellm", "google-genai"):
        for line in text.splitlines():
            s = line.strip().lower()
            if s.startswith(banned) or s.startswith(f'"{banned}'):
                raise AssertionError(f"banned dep {line}")
    print("OK V7 no vendor SDK")


def test_v8_system_has_harness() -> None:
    sys_ = FlowChartCharterSystem(seed=24)
    assert isinstance(sys_.harness, HarnessKernel)
    assert isinstance(sys_.harness.kill, KillSwitch)
    assert isinstance(sys_.harness.sandbox, ExecutionSandbox)
    assert isinstance(sys_.harness.notebook, DurableNotebook)
    assert sys_.harness.kill.armed is True
    print("OK V8 system.harness ARMED")


def test_good_action_then_done() -> None:
    k = HarnessKernel()
    worker = WorkerNode("H4", "Release_Operator", {"github_pr": 1.0})
    out = k.run_action("ActionUnit_GitHubPR", worker, GOOD_PR, unit_id="U_OK")
    assert out["status"] == "SUCCESS_DRY_RUN", out
    claim = k.claim_done(True, required=1)
    assert claim["done"] is True
    assert claim["rejected"] is False
    print("OK done after valid dry-run")


def main() -> None:
    test_version()
    test_v1_halt_blocks_action()
    test_v2_model_cannot_lie_done()
    test_v3_schema_fear()
    test_v4_notebook_record()
    test_v5_retrieval_honest()
    test_v6_scenario_alias()
    test_v7_no_vendor_sdk()
    test_v8_system_has_harness()
    test_good_action_then_done()
    print("ALL v2.4 HARNESS TESTS PASSED")


if __name__ == "__main__":
    main()
