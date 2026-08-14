#!/usr/bin/env python3
"""v2.9 Passage retrieve + supersede."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["FCC_HARNESS_PERSIST"] = "0"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    FlowChartCharterSystem,
    RetrievalHit,
    RetrievalResult,
    __version__,
)


def test_version() -> None:
    assert __version__.startswith("2.") or __version__.startswith("3."), __version__
    print("OK version", __version__)


def test_v1_units_find_episode() -> None:
    sys_ = FlowChartCharterSystem(seed=29)
    sys_.execute_charter("CitationProbe")
    hit = sys_.harness.retrieve("CitationProbe", mode="units")
    assert hit.backend == "fcc_units"
    assert hit.claimed_graphrag is False
    blob = " ".join(h.snippet + h.title + h.id for h in hit.hits).lower()
    assert "citationprobe" in blob
    assert all(h.source for h in hit.hits)
    print("OK V1 units", hit.hits[0].source if hit.hits else None)


def test_v2_fusion_includes_passage() -> None:
    sys_ = FlowChartCharterSystem(seed=29)
    sys_.execute_charter("CitationProbe")
    hit = sys_.harness.retrieve("CitationProbe", mode="fusion")
    assert hit.backend == "fcc_fusion"
    blob = " ".join(h.snippet + h.source for h in hit.hits).lower()
    assert "citationprobe" in blob or any(
        str(h.source).startswith("TU-") for h in hit.hits
    )
    print("OK V2 fusion passages", len(hit.hits))


def test_v3_supersede() -> None:
    sys_ = FlowChartCharterSystem(seed=29)
    sys_.execute_charter("CitationProbe")
    first = [
        u["unit_id"]
        for u in sys_.knowledge.data["text_units"]
        if u.get("valid", True)
    ]
    sys_.execute_charter("CitationProbe")
    units = sys_.knowledge.data["text_units"]
    valid = [u for u in units if u.get("valid", True)]
    invalid = [u for u in units if not u.get("valid", True)]
    assert invalid, "first episode should be superseded"
    assert valid, "new episode should be valid"
    assert first[0] in {u["unit_id"] for u in invalid}
    hit = sys_.harness.retrieve("CitationProbe", mode="units")
    ids = {h.id for h in hit.hits}
    assert first[0] not in ids
    print("OK V3 supersede", len(invalid), len(valid))


def test_v4_stale_fails() -> None:
    sys_ = FlowChartCharterSystem(seed=29)
    sys_.execute_charter("CitationProbe")
    sys_.execute_charter("CitationProbe")
    dead = next(
        u["unit_id"]
        for u in sys_.knowledge.data["text_units"]
        if not u.get("valid", True)
    )
    fake = RetrievalResult(
        backend="fcc_units",
        mode="units",
        hits=[
            RetrievalHit(
                id=dead, title="old", snippet="x", score=1.0, source=dead
            )
        ],
    )
    stamped = sys_.harness.retrieval._stamp_rhythm(fake)
    issues = (stamped.rhythm_audit or {}).get("blocking_issues") or []
    assert "stale_hit" in issues
    print("OK V4 stale_hit")


def test_v5_simple_and_honest() -> None:
    sys_ = FlowChartCharterSystem(seed=29)
    hit = sys_.harness.retrieve("what is FlowChartCharter", mode="simple")
    assert hit.backend == "muscle_memory"
    units = sys_.harness.retrieve("CitationProbe", mode="units")
    assert units.claimed_graphrag is False
    print("OK V5 SIMPLE + honesty")


def main() -> None:
    test_version()
    test_v1_units_find_episode()
    test_v2_fusion_includes_passage()
    test_v3_supersede()
    test_v4_stale_fails()
    test_v5_simple_and_honest()
    print("ALL v2.9 PASSAGE TESTS PASSED")


if __name__ == "__main__":
    main()
