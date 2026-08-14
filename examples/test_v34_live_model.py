#!/usr/bin/env python3
"""v3.3 LiveModel Port — honest degrade, auto-detect, no fake billed call."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["FCC_HARNESS_PERSIST"] = "0"
os.environ["FCC_LLM_PROVIDER"] = "mock"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import LiveModel, detect_live_provider, __version__  # noqa: E402
from flowchartcharter.llm_bridge import detect_live_provider as det  # noqa: E402


def test_version() -> None:
    assert __version__.startswith("3."), __version__
    print("OK version", __version__)


def test_v1_mock_status() -> None:
    os.environ["FCC_LLM_PROVIDER"] = "mock"
    brain = LiveModel.from_env()
    st = brain.status()
    assert st["live"] is False
    assert st["reduce_mode"] == "extractive"
    out = brain.complete("hello")
    assert out["live"] is False
    assert out["reason"] == "port_not_live_mock_contract"
    print("OK V1 mock degrade")


def test_v2_autodetect_xai() -> None:
    os.environ.pop("FCC_LLM_PROVIDER", None)
    os.environ["XAI_API_KEY"] = "xai-not-a-real-spend-key"
    try:
        assert detect_live_provider() == "xai"
        cfg_live = LiveModel.from_env().status()
        assert cfg_live["provider"] == "xai"
        assert cfg_live["key_present"] is True
        # complete would HTTP — do not call with fake key
    finally:
        os.environ.pop("XAI_API_KEY", None)
        os.environ["FCC_LLM_PROVIDER"] = "mock"
    print("OK V2 autodetect xai")


def test_v3_forced_mock_wins() -> None:
    os.environ["FCC_LLM_PROVIDER"] = "mock"
    os.environ["XAI_API_KEY"] = "xai-not-a-real-spend-key"
    try:
        assert det() == "mock"
    finally:
        os.environ.pop("XAI_API_KEY", None)
    print("OK V3 forced mock")


def main() -> None:
    test_version()
    test_v1_mock_status()
    test_v2_autodetect_xai()
    test_v3_forced_mock_wins()
    print("ALL v3.4 LIVE MODEL TESTS PASSED")


if __name__ == "__main__":
    main()
