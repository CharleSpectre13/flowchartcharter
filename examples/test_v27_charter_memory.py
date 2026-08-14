#!/usr/bin/env python3
"""v2.7 Incremental Charter Memory — delta ingest, lazy query, honest port."""
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
    RetrievalPort,
    __version__,
    extract_triples,
    ingest_text,
    run_reindex_loop,
    verify_extraction,
)


def test_version() -> None:
    assert __version__[0] in "23", __version__
    print("OK version", __version__)


def test_v1_delta_no_rebuild() -> None:
    kg = KnowledgeGraph()
    before = kg.entity_count()
    a = ingest_text(
        kg,
        "FlowChartCharter uses Rhythm Markers.",
        source_id="doc-a",
    )
    mid = kg.entity_count()
    b = ingest_text(
        kg,
        "DeltaNotebook stores charter receipts. "
        "DeltaNotebook depends on DurableNotebook.",
        source_id="doc-b",
    )
    after = kg.entity_count()
    assert a["ok"] and b["ok"]
    assert after > mid >= before
    assert kg.data.get("full_rebuild") is False
    assert b["merge"]["full_rebuild"] is False
    print("OK V1 delta ingest", before, mid, after)


def test_v2_retrieve_new_fact() -> None:
    kg = KnowledgeGraph()
    ingest_text(
        kg,
        "DeltaNotebook stores charter receipts.",
        source_id="doc-b",
    )
    port = RetrievalPort(kg=kg)
    hit = port.retrieve("DeltaNotebook", mode="lazy")
    titles = " ".join(h.title for h in hit.hits)
    ids = " ".join(h.id for h in hit.hits)
    assert "delta" in (titles + ids).lower()
    assert hit.claimed_graphrag is False
    assert hit.backend in ("fcc_lazy", "fcc_kg_delta")
    assert hit.rebuild is False
    print("OK V2 retrieve", hit.backend, len(hit.hits))


def test_v3_no_false_graphrag() -> None:
    kg = KnowledgeGraph()
    ingest_text(kg, "DeltaNotebook stores charter receipts.", source_id="b")
    port = RetrievalPort(kg=kg)
    hit = port.retrieve("DeltaNotebook", mode="local")
    assert hit.claimed_graphrag is False
    rhythm = hit.rhythm_audit or {}
    ev = rhythm.get("evidence") or {}
    assert ev.get("claimed_graphrag") is False
    assert ev.get("rebuild") is False
    print("OK V3 honesty", hit.backend)


def test_v4_maker_checker_reindex() -> None:
    proposed = extract_triples(
        "DeltaNotebook stores charter receipts.",
        implementor_role="Extractor",
    )
    bad = verify_extraction(
        proposed,
        implementor_role="Audit Manager",
        auditor_role="Audit Manager",
    )
    assert bad.accepted is False
    assert "maker_checker_violation" in bad.issues
    kg = KnowledgeGraph()
    report = run_reindex_loop(
        kg,
        [{"text": "DeltaNotebook stores charter receipts.", "source_id": "x"}],
        implementor_role="Extractor",
        auditor_role="Audit Manager",
    )
    assert report["ok"] is True
    assert report["full_rebuild"] is False
    assert report["claimed_graphrag"] is False
    print("OK V4 reindex maker-checker")


def test_v5_system_ingest() -> None:
    sys_ = FlowChartCharterSystem(seed=27)
    before = sys_.knowledge.entity_count()
    out = sys_.ingest_memory(
        "DeltaNotebook stores charter receipts.",
        source_id="sys-b",
    )
    assert out["ok"] is True
    assert sys_.knowledge.entity_count() > before
    hit = sys_.harness.retrieve("DeltaNotebook", mode="lazy")
    assert hit.claimed_graphrag is False
    blob = " ".join(h.title + h.id for h in hit.hits).lower()
    assert "delta" in blob
    print("OK V5 system ingest + harness retrieve")


def main() -> None:
    test_version()
    test_v1_delta_no_rebuild()
    test_v2_retrieve_new_fact()
    test_v3_no_false_graphrag()
    test_v4_maker_checker_reindex()
    test_v5_system_ingest()
    print("ALL v2.7 CHARTER MEMORY TESTS PASSED")


if __name__ == "__main__":
    main()
