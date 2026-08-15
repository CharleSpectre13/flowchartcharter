#!/usr/bin/env python3
"""v3.4 First-day house — starter notes, drip, shelves, offline receipt."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["FCC_HARNESS_PERSIST"] = "0"
os.environ["FCC_LLM_PROVIDER"] = "mock"
os.environ["FCC_OLLAMA"] = "0"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    FlowChartCharterSystem,
    STARTER_CHARTER,
    __version__,
    ask_world,
    verify_receipt_path,
)
from flowchartcharter.llm_bridge import detect_live_provider  # noqa: E402


def test_version() -> None:
    assert __version__.startswith("3.4"), __version__
    print("OK version", __version__)


def test_v1_first_day_not_blank() -> None:
    sys_ = FlowChartCharterSystem(seed=15)
    out = sys_.first_day()
    assert out["ok"] is True
    assert out["charter"] == STARTER_CHARTER
    assert out["claimed_graphrag"] is False
    assert out["seed"]["text_units"] >= 3
    again = sys_.first_day()
    assert again["seed"]["seeded"] is False
    print("OK V1 first day", out["seed"]["text_units"])


def test_v2_drip_remember() -> None:
    sys_ = FlowChartCharterSystem(seed=16)
    sys_.first_day()
    rec = sys_.remember("We keep Grok on the phone. The house is ours.")
    assert rec["ok"] is True
    empty = sys_.remember("   ")
    assert empty["ok"] is False
    print("OK V2 remember")


def test_v3_world_mouth_none() -> None:
    out = ask_world("What is a charter?")
    assert out["shelf"] == "none"
    assert out["live"] is False
    assert out["claimed_graphrag"] is False
    print("OK V3 mouth none")


def test_v4_receipt_offline() -> None:
    sys_ = FlowChartCharterSystem(seed=17)
    day = sys_.first_day()
    rec = day["receipt"]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(rec, fh)
        path = fh.name
    ok = verify_receipt_path(path)
    assert ok["ok"] is True
    rec["hash"] = "dead"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    bad = verify_receipt_path(path)
    assert bad["ok"] is False
    print("OK V4 stranger file")


def test_v5_ollama_not_required() -> None:
    os.environ["FCC_LLM_PROVIDER"] = "mock"
    assert detect_live_provider() == "mock"
    print("OK V5 ollama off")


def main() -> None:
    test_version()
    test_v1_first_day_not_blank()
    test_v2_drip_remember()
    test_v3_world_mouth_none()
    test_v4_receipt_offline()
    test_v5_ollama_not_required()
    print("ALL v3.5 HOUSE TESTS PASSED")


if __name__ == "__main__":
    main()
