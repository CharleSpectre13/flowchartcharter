#!/usr/bin/env python3
"""v2.8 Citation Law + Episode Bind."""
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
    RetrievalHit,
    RetrievalPort,
    RetrievalResult,
    __version__,
    ingest_text,
)


def test_version() -> None:
    assert __version__[0] in "23", __version__
    print("OK version", __version__)


def test_v1_episode_on_charter() -> None:
    sys_ = FlowChartCharterSystem(seed=28)
    before_u = len(sys_.knowledge.data.get("text_units") or [])
    before_e = sys_.knowledge.entity_count()
    snap = sys_.execute_charter("CitationProbe")
    after_u = len(sys_.knowledge.data.get("text_units") or [])
    ep = snap.get("episode") or {}
    assert after_u > before_u
    assert sys_.knowledge.entity_count() >= before_e
    assert sys_.knowledge.data.get("full_rebuild") is False
    assert ep.get("episode") is True
    assert ep.get("claimed_graphrag") is False
    print("OK V1 episode bind", before_u, after_u)


def test_v2_fusion_cites() -> None:
    kg = KnowledgeGraph()
    ingest_text(kg, "DeltaNotebook stores charter receipts.", source_id="doc-b")
    port = RetrievalPort(kg=kg)
    hit = port.retrieve("DeltaNotebook", mode="fusion")
    assert hit.backend == "fcc_fusion"
    assert hit.claimed_graphrag is False
    assert hit.hits
    assert all(h.source for h in hit.hits)
    assert hit.cited is True
    assert (hit.rhythm_audit or {}).get("passed") is True
    print("OK V2 fusion cited", len(hit.hits))


def test_v3_ungrounded_fails() -> None:
    port = RetrievalPort()
    fake = RetrievalResult(
        backend="fcc_lazy",
        mode="lazy",
        hits=[RetrievalHit(id="x", title="bare", snippet="n", score=1.0, source="")],
        claimed_graphrag=False,
    )
    stamped = port._stamp_rhythm(fake)
    issues = (stamped.rhythm_audit or {}).get("blocking_issues") or []
    assert "ungrounded_hit" in issues
    assert stamped.cited is False
    print("OK V3 ungrounded fails")


def test_v4_simple_stays_muscle() -> None:
    sys_ = FlowChartCharterSystem(seed=28)
    hit = sys_.harness.retrieve("what is FlowChartCharter", mode="simple")
    assert hit.backend == "muscle_memory"
    print("OK V4 SIMPLE muscle")


def test_v5_alias_and_no_graphrag() -> None:
    kg = KnowledgeGraph()
    ingest_text(kg, "DeltaNotebook stores charter receipts.", source_id="a")
    n1 = kg.entity_count()
    ingest_text(kg, "delta_notebook stores more receipts.", source_id="b")
    # alias should not explode unique count for the same concept
    assert kg.resolve_alias("DeltaNotebook") == kg.resolve_alias("delta_notebook")
    port = RetrievalPort(kg=kg)
    hit = port.retrieve("DeltaNotebook", mode="lazy")
    assert hit.claimed_graphrag is False
    print("OK V5 alias", n1, kg.entity_count(), kg.resolve_alias("DeltaNotebook"))


def main() -> None:
    test_version()
    test_v1_episode_on_charter()
    test_v2_fusion_cites()
    test_v3_ungrounded_fails()
    test_v4_simple_stays_muscle()
    test_v5_alias_and_no_graphrag()
    print("ALL v2.8 CITATION TESTS PASSED")


if __name__ == "__main__":
    main()
