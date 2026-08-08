#!/usr/bin/env python3
"""Phase 6 — fcc CLI tests (local mode, no server required)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
os.environ["FCC_LLM_PROVIDER"] = "mock"
os.environ["FCC_LIVE_WIRE"] = "1"

from typer.testing import CliRunner  # noqa: E402

from flowchartcharter.fcc_cli import app, probe_server, resolve_mode  # noqa: E402

runner = CliRunner()
LIB = ROOT / "library" / "unstructured_data_etl.yaml"
HELLO = ROOT / "charterhub" / "playbooks" / "community" / "hello_charter.yaml"


def test_version() -> None:
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0
    assert "1.6" in r.stdout or "flowchart" in r.stdout.lower()
    print("OK version", r.stdout.strip().splitlines()[0])


def test_run_local() -> None:
    r = runner.invoke(app, ["--local", "run", str(LIB)])
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "quality" in r.stdout.lower() or "Execution Result" in r.stdout
    print("OK fcc run --local")


def test_hello_charterhub() -> None:
    r = runner.invoke(app, ["--local", "run", str(HELLO)])
    assert r.exit_code == 0, r.stdout + r.stderr
    print("OK charterhub hello")


def test_monitor_once_local() -> None:
    r = runner.invoke(app, ["--local", "monitor", "--once"])
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "Roster" in r.stdout or "monitor" in r.stdout.lower() or "Active" in r.stdout
    print("OK fcc monitor --once")


def test_sync_local() -> None:
    r = runner.invoke(app, ["--local", "sync"])
    assert r.exit_code == 0, r.stdout + r.stderr
    print("OK fcc sync")


def test_audit_film_local() -> None:
    r = runner.invoke(app, ["--local", "audit-film"])
    assert r.exit_code == 0, r.stdout + r.stderr
    print("OK fcc audit-film")


def test_library_cmd() -> None:
    r = runner.invoke(app, ["--local", "library", "--path", str(ROOT / "library")])
    assert r.exit_code == 0
    assert "secops" in r.stdout or "yaml" in r.stdout
    print("OK fcc library")


def test_submit_local() -> None:
    r = runner.invoke(
        app, ["--local", "submit", "Legacy Code Refactor", "--entropy", "0.3"]
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    print("OK fcc submit")


def test_status_offline_graceful() -> None:
    # point at dead port — should exit 2 gracefully
    r = runner.invoke(app, ["--api", "http://127.0.0.1:59999", "status"])
    assert r.exit_code == 2
    assert "OFFLINE" in r.stdout or "offline" in r.stdout.lower()
    print("OK status offline graceful")


def test_probe_and_resolve() -> None:
    online = probe_server("http://127.0.0.1:59999")
    assert online is False
    mode, sys_obj = resolve_mode("http://127.0.0.1:59999", prefer_local=True)
    assert mode == "local" and sys_obj is not None
    print("OK resolve local fallback")


if __name__ == "__main__":
    test_version()
    test_run_local()
    test_hello_charterhub()
    test_monitor_once_local()
    test_sync_local()
    test_audit_film_local()
    test_library_cmd()
    test_submit_local()
    test_status_offline_graceful()
    test_probe_and_resolve()
    print("ALL_FCC_CLI_TESTS_PASSED")
