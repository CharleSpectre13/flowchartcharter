#!/usr/bin/env python3
"""Serve Master Dashboard + FlowChartCharter API on one process.

Hooks the static Live Sandbox UI into FastAPI endpoints:
  /workload/submit · /system/trigger-monday-sync · /system/load-playbook
  /metrics (Prometheus) · /library/* (enterprise playbooks)

Usage:
  PYTHONPATH=packages/core python scripts/serve_dashboard.py
  # → http://0.0.0.0:8090/  (dashboard)
  # → http://0.0.0.0:8090/docs
  # → http://0.0.0.0:8090/metrics
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.api_server import create_app, main as api_main  # noqa: E402


def build_app():
    """Factory used by uvicorn / tests — same as api create_app (static mounted)."""
    return create_app()


if __name__ == "__main__":
    os.environ.setdefault("FCC_HOST", "0.0.0.0")
    os.environ.setdefault("FCC_PORT", "8090")
    # Prefer repo dashboard + library paths
    os.environ.setdefault("FCC_DASHBOARD_DIR", str(ROOT / "dashboard"))
    os.environ.setdefault("FCC_LIBRARY_DIR", str(ROOT / "library"))
    api_main()
