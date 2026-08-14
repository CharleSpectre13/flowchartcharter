#!/usr/bin/env python3
"""v3.3 Strengthen weak spots — extract, persist, sandbox, stranger receipt."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["FCC_HARNESS_PERSIST"] = "0"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    FlowChartCharterSystem,
    KnowledgeGraph,
    __version__,
    extract_triples,
    verify_chain,
)
from flowchartcharter.execution_sandbox import ExecutionSandbox  # noqa: E402


def test_version() -> None:
    assert __version__ == "3.3.0", __version__
    print("OK version", __version__)


def test_v1_extract_relation() -> None:
    prop = extract_triples(
        "AlphaRiver irrigation fails when silt blocks the intake."
    )
    types = {r["type"] for r in prop.relations}
    titles = {e["title"].lower() for e in prop.entities}
    assert "fails_when" in types or "blocks" in types
    assert any("alpha" in t for t in titles)
    print("OK V1 extract", types)


def test_v2_kg_persist_roundtrip(tmp_path: Path | None = None) -> None:
    dest = Path("/tmp/fcc_kg_delta_test.json")
    kg = KnowledgeGraph()
    from flowchartcharter import ingest_text

    ingest_text(kg, "AlphaRiver irrigation fails when silt blocks.", source_id="p")
    kg.save_delta(dest)
    kg2 = KnowledgeGraph()
    out = kg2.load_delta(dest)
    assert out["ok"] is True
    assert kg2.data.get("full_rebuild") is False
    assert any(
        "alphariver" in str(u.get("text") or "").lower()
        for u in kg2.data.get("text_units") or []
    )
    dest.unlink(missing_ok=True)
    print("OK V2 kg persist")


def test_v3_stranger_chain() -> None:
    sys_ = FlowChartCharterSystem(seed=33)
    a = sys_.issue_stranger_receipt()
    b = sys_.issue_stranger_receipt()
    assert verify_chain([a, b])
    assert a.get("claimed_graphrag") is False
    assert a.get("policy_not_kernel") is True
    tampered = dict(b)
    tampered["text_units"] = 999
    assert verify_chain([a, tampered]) is False
    print("OK V3 stranger chain")


def test_v4_sandbox_deny() -> None:
    box = ExecutionSandbox()
    assert box.allow("shell", halted=False) == "action_denied_by_default"
    assert box.allow("file_write", halted=False) == "action_denied_by_default"
    assert box.policy_not_kernel() is True
    print("OK V4 sandbox deny")


def test_v5_qfs_extractive_stamp() -> None:
    sys_ = FlowChartCharterSystem(seed=33)
    sys_.ingest_memory("AlphaRiver silt blocks the intake.", source_id="a")
    pack = sys_.knowledge.qfs_search("AlphaRiver")
    assert pack.get("reduce_mode") == "extractive"
    assert pack.get("backend") == "fcc_qfs"
    print("OK V5 reduce_mode extractive")


def main() -> None:
    test_version()
    test_v1_extract_relation()
    test_v2_kg_persist_roundtrip()
    test_v3_stranger_chain()
    test_v4_sandbox_deny()
    test_v5_qfs_extractive_stamp()
    print("ALL v3.3 STRENGTHEN TESTS PASSED")


if __name__ == "__main__":
    main()
