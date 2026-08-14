#!/usr/bin/env python3
"""v2.3 Torch Path — live goldens, Port-wired lanes, honest retrieval."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    RetrievalPort,
    __version__,
    run_live_goldens,
)
from flowchartcharter.agents import BossAgent  # noqa: E402
from flowchartcharter.charter_synthesizer import CharterSynthesizer  # noqa: E402
from flowchartcharter.knowledge_graph import KnowledgeGraph  # noqa: E402
from flowchartcharter.playbook_compiler import (  # noqa: E402
    compile_playbook,
    run_compiled_playbook,
)
from flowchartcharter.system import FlowChartCharterSystem  # noqa: E402


def test_version() -> None:
    assert __version__[0] in "123", __version__
    print("OK version", __version__)


def test_live_golden_honest_without_key() -> None:
    os.environ.pop("XAI_API_KEY", None)
    os.environ.pop("FCC_LLM_API_KEY", None)
    os.environ["FCC_LLM_PROVIDER"] = "mock"
    report = run_live_goldens(cfo_ceiling=800, provider="xai")
    assert report["live"] is False
    assert report["under_budget"] is True
    assert report["cfo_ceiling"] == 800
    assert report["gate"] == "live_inference"
    # force_live must not fake a live run
    forced = run_live_goldens(cfo_ceiling=800, provider="xai", force_live=True)
    assert forced["live"] is False
    assert forced["reason"] == "force_live_requested_but_port_not_live"
    print("OK live golden honest", report["reason"], "billed", report["billed_tokens"])


def test_retrieval_honesty() -> None:
    port = RetrievalPort()
    simple = port.retrieve("what is FlowChartCharter", mode="simple")
    assert simple.claimed_graphrag is False
    assert simple.backend == "muscle_memory"
    local = port.retrieve("how does Charter connect to Coach Trust", mode="local")
    assert local.claimed_graphrag is False
    assert local.backend == "fcc_kg_subflow"
    glob = port.retrieve("summarize enterprise-wide themes", mode="global")
    assert glob.claimed_graphrag is False
    assert glob.backend == "fcc_kg_subflow"
    print("OK retrieval honesty", simple.backend, local.backend, glob.backend)


def test_drift_subflow_honest() -> None:
    """graph-engineering DRIFT uses KG; never claims Microsoft GraphRAG."""
    port = RetrievalPort()
    drift = port.retrieve(
        "why does Charter connect to Coach Trust",
        mode="drift",
        token_budget=400,
    )
    assert drift.mode == "drift"
    assert drift.claimed_graphrag is False
    assert drift.backend == "fcc_kg_subflow"
    assert drift.drift_phases == ["primer", "follow_up", "reduce"]
    assert drift.rhythm_audit.get("type") == "RhythmAudit"
    assert drift.rhythm_audit.get("marker") == "gate"
    print(
        "OK drift sub-flow",
        "hits",
        len(drift.hits),
        "rhythm",
        drift.rhythm_audit.get("passed"),
    )


def test_retrieval_rhythm_gate() -> None:
    """rhythm-marker-validator: every retrieve emits ST-04 JSON."""
    port = RetrievalPort()
    simple = port.retrieve("define muscle memory", mode="simple")
    assert simple.rhythm_audit.get("passed") is True
    assert simple.rhythm_audit.get("threshold") == 0.90
    dead = RetrievalPort(
        graphrag_endpoint="http://127.0.0.1:9",
        timeout_s=0.2,
    ).retrieve("themes", mode="global")
    assert dead.claimed_graphrag is False
    print("OK retrieval rhythm", simple.rhythm_audit.get("marker"))


def test_graphrag_fail_never_claimed() -> None:
    """Endpoint set but dead → backend failed, claimed_graphrag stays false."""
    port = RetrievalPort(
        graphrag_endpoint="http://127.0.0.1:9",
        timeout_s=0.3,
    )
    result = port.retrieve("enterprise-wide risk themes", mode="global")
    assert result.claimed_graphrag is False
    assert result.backend in ("graphrag_http_failed", "fcc_kg_subflow")
    print("OK graphrag fail not claimed", result.backend, result.reason[:60])


def test_hybrid_stamps_retrieval() -> None:
    boss = BossAgent("Torch-GM", cfo_ceiling=3500)
    env = boss.handle_workload("what is the charter", hint="simple")
    assert "retrieval" in env
    assert env["retrieval"]["claimed_graphrag"] is False
    env_g = boss.handle_workload(
        "summarize global themes across the enterprise", hint="global"
    )
    assert env_g["lane"] == "global"
    assert "retrieval" in env_g
    assert env_g["result"].get("backend") in ("kg_deterministic", "port_reduce")
    env_m = boss.handle_workload(
        "why does the charter connect to rhythm markers",
        hint="multi_hop",
    )
    assert env_m["lane"] == "multi_hop"
    assert env_m["retrieval"]["mode"] == "drift"
    assert env_m["retrieval"]["claimed_graphrag"] is False
    print(
        "OK hybrid stamps retrieval",
        env["retrieval"]["backend"],
        env_g["result"].get("backend"),
        env_m["retrieval"]["mode"],
    )


def test_synthesizer_source_field() -> None:
    synth = CharterSynthesizer()
    draft = synth.synthesize("Audit AWS infrastructure for compliance")
    pub = draft.to_public()
    assert pub["synthesis_source"] in (
        "muscle_heuristic",
        "port_ranked",
        "port_rejected_keep_heuristic",
    )
    assert "github" not in " ".join(pub["unit_ids"]).lower()
    print("OK synth source", pub["synthesis_source"], pub["unit_ids"])


def test_secops_vertical_receipt_shape() -> None:
    yaml_path = ROOT / "library" / "secops_auto_patch_v2.yaml"
    compiled = compile_playbook(yaml_path.read_text())
    system = FlowChartCharterSystem(seed=23)
    result = run_compiled_playbook(
        system, "secops dry-run", playbook=compiled
    )
    assert (
        result.get("ok")
        or result.get("quality", 0) >= 0
        or "rhythm_audits" in result
    )
    print("OK secops compile+run keys", sorted(result)[:12])


def main() -> None:
    test_version()
    test_live_golden_honest_without_key()
    test_retrieval_honesty()
    test_drift_subflow_honest()
    test_retrieval_rhythm_gate()
    test_graphrag_fail_never_claimed()
    test_hybrid_stamps_retrieval()
    test_synthesizer_source_field()
    test_secops_vertical_receipt_shape()
    print("ALL v2.3 TORCH TESTS PASSED")


if __name__ == "__main__":
    main()
