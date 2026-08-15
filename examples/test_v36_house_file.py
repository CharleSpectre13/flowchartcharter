#!/usr/bin/env python3
"""v3.4 house file + signed receipt + Halt on mouth."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["FCC_LLM_PROVIDER"] = "mock"
os.environ["FCC_OLLAMA"] = "0"
os.environ["FCC_STARTER_HOUSE"] = "1"
os.environ["FCC_HOUSE_SIGN"] = "1"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))


def test_v1_file_survives() -> None:
    tmp = tempfile.mkdtemp(prefix="fcc-house-")
    os.environ["FCC_HARNESS_PERSIST"] = "1"
    os.environ["FCC_HOUSE_PATH"] = str(Path(tmp) / "house.jsonl")
    from flowchartcharter.house import dispatch, house_path

    a = dispatch("first-day")
    assert a["ok"] and a["seed"]["text_units"] >= 3
    b = dispatch("remember", "The phone stays optional.")
    assert b["ok"]
    assert house_path().is_file()
    c = dispatch("status")
    assert c["shelves"]["text_units"] >= 4
    print("OK V1 file", c["shelves"]["text_units"])


def test_v2_welcome_on_open() -> None:
    tmp = tempfile.mkdtemp(prefix="fcc-house-")
    os.environ["FCC_HARNESS_PERSIST"] = "1"
    os.environ["FCC_HOUSE_PATH"] = str(Path(tmp) / "house.jsonl")
    from flowchartcharter.system import FlowChartCharterSystem

    s = FlowChartCharterSystem(seed=3)
    units = (s.knowledge.data or {}).get("text_units") or []
    assert len(units) >= 3
    print("OK V2 welcome", len(units))


def test_v3_sig_and_halt() -> None:
    tmp = tempfile.mkdtemp(prefix="fcc-house-")
    os.environ["FCC_HARNESS_PERSIST"] = "1"
    os.environ["FCC_HOUSE_PATH"] = str(Path(tmp) / "house.jsonl")
    from flowchartcharter.house import dispatch, verify_receipt_path, house_path
    from flowchartcharter.stranger_receipt import issue_receipt
    from flowchartcharter.system import FlowChartCharterSystem

    day = dispatch("first-day")
    rec = day["receipt"]
    assert rec.get("sig") and rec.get("pub")
    path = house_path()
    out = verify_receipt_path(str(path))
    assert out["hash_ok"] is True
    assert out["sig"] == "sig_ok"
    halt = dispatch("halt")
    assert halt["halted"] is True
    ask = dispatch("ask", "hello")
    assert ask.get("halted") is True or ask.get("shelf") == "none"
    dispatch("arm")
    print("OK V3 sig+halt", out["sig"])
    os.environ["FCC_HARNESS_PERSIST"] = "0"
    s = FlowChartCharterSystem(seed=9)
    bare = issue_receipt(s)
    assert not bare.get("sig")
    print("OK V3b sig_absent when persist off")


def main() -> None:
    test_v1_file_survives()
    test_v2_welcome_on_open()
    test_v3_sig_and_halt()
    print("ALL v3.6 HOUSE FILE TESTS PASSED")


if __name__ == "__main__":
    main()
