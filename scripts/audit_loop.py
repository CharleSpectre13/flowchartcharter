#!/usr/bin/env python3
"""Continuous audit loop for FlowChartCharter Python packages.

loop-engineer + pep8-python-code-reviewer:
  1. pycodestyle (max-line-length=100)
  2. pyflakes
  3. compileall
  4. example test suite (subset or all)
  5. write CXR markdown under 07_CROSS_REFERENCE_REPORTS/

Usage:
  python3 scripts/audit_loop.py
  python3 scripts/audit_loop.py --tests examples/test_api_server.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packages" / "core" / "flowchartcharter"
REPORTS = ROOT / "07_CROSS_REFERENCE_REPORTS"
MAX_LINE = "100"

DEFAULT_TARGETS = [
    str(PKG / "api_server.py"),
    str(PKG / "llm_bridge.py"),
    str(PKG / "analytics.py"),
    str(PKG / "living_playbook.py"),
    str(PKG / "fitness.py"),
    str(PKG / "agents.py"),
    str(PKG / "system.py"),
    str(PKG / "elastic.py"),
    str(PKG / "reference_engine.py"),
    str(PKG / "system_audit.py"),
    str(PKG / "harness.py"),
]


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def main() -> int:
    parser = argparse.ArgumentParser(description="FCC continuous audit loop")
    parser.add_argument(
        "--tests",
        nargs="*",
        default=[
            "examples/test_api_server.py",
            "examples/test_analytics_protocol.py",
            "examples/test_living_playbook.py",
            "examples/test_audit_patches.py",
        ],
        help="Test scripts to execute",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        default=DEFAULT_TARGETS,
        help="Python files for pep8/pyflakes",
    )
    args = parser.parse_args()

    results: list[tuple[str, int, str]] = []

    # 1. pycodestyle
    code, out = run(
        [
            sys.executable,
            "-m",
            "pycodestyle",
            f"--max-line-length={MAX_LINE}",
            "--ignore=E203,W503,E501,E704",
            *args.targets,
        ]
    )
    results.append(("pycodestyle", code, out.strip()))

    # 2. pyflakes
    code, out = run([sys.executable, "-m", "pyflakes", *args.targets])
    results.append(("pyflakes", code, out.strip()))

    # 3. compileall
    code, out = run(
        [sys.executable, "-m", "compileall", "-q", str(PKG)]
    )
    results.append(("compileall", code, out.strip()))

    # 4. tests
    env_pythonpath = str(ROOT / "packages" / "core")
    for test in args.tests:
        tpath = ROOT / test if not Path(test).is_absolute() else Path(test)
        if not tpath.exists():
            results.append((f"test:{test}", 1, "MISSING"))
            continue
        p = subprocess.run(
            [sys.executable, str(tpath)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env={**dict(os.environ), "PYTHONPATH": env_pythonpath},
        )
        tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
        results.append(
            (f"test:{tpath.name}", p.returncode, "\n".join(tail[-8:]))
        )

    passed = all(c == 0 for _, c, _ in results)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS / f"CXR-{ts}-audit-loop.md"

    lines = [
        f"# CXR Audit Loop — {ts}",
        "",
        f"**Verdict: {'PASS' if passed else 'FAIL'}**",
        "",
        "| Check | Exit | Notes |",
        "|-------|------|-------|",
    ]
    for name, code, out in results:
        note = "clean" if code == 0 else (out[:120].replace("\n", " ") or "error")
        lines.append(f"| {name} | {code} | {note} |")
    lines.append("")
    lines.append("## Details")
    for name, code, out in results:
        lines.append(f"### {name} (exit {code})")
        lines.append("```")
        lines.append(out or "(no output)")
        lines.append("```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"AUDIT_LOOP {'PASS' if passed else 'FAIL'} → {report_path}")
    for name, code, out in results:
        status = "OK" if code == 0 else "FAIL"
        print(f"  [{status}] {name}")
        if code != 0 and out:
            print("   ", out[:200].replace("\n", " | "))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
