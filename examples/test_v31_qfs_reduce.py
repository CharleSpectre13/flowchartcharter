#!/usr/bin/env python3
"""v3.1 Structured QFS reduce — partials + no invented synthesis."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["FCC_HARNESS_PERSIST"] = "0"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    KnowledgeGraph,
    RetrievalPort,
    RetrievalResult,
    __version__,
    ingest_text,
)


def _two_themes() -> KnowledgeGraph:
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
    return kg


def test_version() -> None:
    assert __version__.startswith("3."), __version__
    print("OK version", __version__)


def test_v1_partials_exist() -> None:
    kg = _two_themes()
    pack = kg.qfs_search("overall theme of AlphaRiver")
    assert pack.get("partials")
    bags = {p["bag"] for p in pack["partials"]}
    assert "theme-a" in bags
    assert "theme-b" not in bags
    print("OK V1 partials", bags)


def test_v2_helpfulness_zero_dropped() -> None:
    kg = _two_themes()
    pack = kg.qfs_search("AlphaRiver")
    helps = {p["bag"]: p["helpfulness"] for p in pack["partials"]}
    assert helps.get("theme-a", 0) > 0
    assert "theme-b" not in helps
    print("OK V2 helpfulness", helps)


def test_v3_reduce_subset() -> None:
    kg = _two_themes()
    pack = kg.qfs_search("AlphaRiver irrigation")
    allowed = set()
    for part in pack["partials"]:
        allowed.update(part["sentences"])
    for sent in pack["synthesis"].split(". "):
        chunk = sent.strip().rstrip(".")
        if len(chunk) < 8:
            continue
        assert any(chunk in a or a.startswith(chunk) for a in allowed), chunk
    print("OK V3 reduce subset")


def test_v4_invented_fails() -> None:
    port = RetrievalPort()
    fake = RetrievalResult(
        backend="fcc_qfs",
        mode="global",
        hits=[],
        synthesis="The moon is made of cheese.",
        partials=[
            {
                "bag": "theme-a",
                "helpfulness": 80,
                "sentences": ["AlphaRiver irrigation fails."],
            }
        ],
        claimed_graphrag=False,
    )
    stamped = port._stamp_rhythm(fake)
    issues = (stamped.rhythm_audit or {}).get("blocking_issues") or []
    assert "reduce_invented" in issues
    print("OK V4 reduce_invented")


def test_v5_honest() -> None:
    port = RetrievalPort(kg=_two_themes())
    hit = port.retrieve("AlphaRiver", mode="global")
    assert hit.backend == "fcc_qfs"
    assert hit.claimed_graphrag is False
    assert hit.partials
    print("OK V5 honest qfs", len(hit.partials))


def main() -> None:
    test_version()
    test_v1_partials_exist()
    test_v2_helpfulness_zero_dropped()
    test_v3_reduce_subset()
    test_v4_invented_fails()
    test_v5_honest()
    print("ALL v3.1 QFS REDUCE TESTS PASSED")


if __name__ == "__main__":
    main()
