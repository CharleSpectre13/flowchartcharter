#!/usr/bin/env python3
"""v3.0 Extractive QFS — theme briefs cite passages."""
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
    ingest_text,
)


def test_version() -> None:
    assert __version__.startswith("3."), __version__
    print("OK version", __version__)


def test_v1_fresh_global_unchanged() -> None:
    port = RetrievalPort()
    hit = port.retrieve("summarize enterprise-wide themes", mode="global")
    assert hit.backend == "fcc_kg_subflow"
    assert hit.claimed_graphrag is False
    print("OK V1 fresh global fallback")


def test_v2_qfs_not_title_join() -> None:
    kg = KnowledgeGraph()
    titles = " | ".join(
        r.get("executive_summary", "")
        for r in list(kg.data["community_reports"].values())[:4]
    )
    ingest_text(
        kg,
        "AlphaRiver irrigation fails when silt blocks the intake.",
        source_id="theme-a",
    )
    port = RetrievalPort(kg=kg)
    hit = port.retrieve("overall theme of AlphaRiver", mode="global")
    assert hit.backend == "fcc_qfs"
    blob = " ".join(h.snippet for h in hit.hits)
    assert blob != titles
    assert "alphariver" in blob.lower()
    assert all(h.source for h in hit.hits)
    print("OK V2 qfs not title-join")


def test_v3_theme_isolation() -> None:
    kg = KnowledgeGraph()
    ingest_text(
        kg,
        "AlphaRiver irrigation fails when silt blocks the intake.",
        source_id="theme-a",
    )
    ingest_text(
        kg,
        "BetaHarbor shipping delays when fog closes the channel.",
        source_id="theme-b",
    )
    port = RetrievalPort(kg=kg)
    hit = port.retrieve("overall theme of AlphaRiver", mode="global")
    blob = " ".join(h.snippet + h.source for h in hit.hits).lower()
    assert "alphariver" in blob
    assert "betaharbor" not in blob
    assert hit.claimed_graphrag is False
    print("OK V3 theme isolation")


def test_v4_stale_excluded() -> None:
    sys_ = FlowChartCharterSystem(seed=30)
    sys_.ingest_memory(
        "AlphaRiver irrigation fails when silt blocks the intake.",
        source_id="theme-a",
    )
    sys_.ingest_memory(
        "AlphaRiver irrigation is restored after the dredge.",
        source_id="theme-a",
    )
    hit = sys_.harness.retrieve("AlphaRiver irrigation", mode="global")
    blob = " ".join(h.snippet for h in hit.hits).lower()
    assert "dredge" in blob
    assert "silt blocks" not in blob
    print("OK V4 stale excluded")


def test_v5_system_qfs() -> None:
    sys_ = FlowChartCharterSystem(seed=30)
    sys_.ingest_memory(
        "AlphaRiver irrigation fails when silt blocks the intake.",
        source_id="theme-a",
    )
    hit = sys_.harness.retrieve("AlphaRiver", mode="global")
    assert hit.backend == "fcc_qfs"
    assert hit.claimed_graphrag is False
    print("OK V5 system qfs")


def main() -> None:
    test_version()
    test_v1_fresh_global_unchanged()
    test_v2_qfs_not_title_join()
    test_v3_theme_isolation()
    test_v4_stale_excluded()
    test_v5_system_qfs()
    print("ALL v3.0 QFS TESTS PASSED")


if __name__ == "__main__":
    main()
