"""CLI helpers for package distribution (fcc-audit entrypoint)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def audit_main() -> None:
    """Run pep8 + pyflakes + compileall against the installed package."""
    try:
        import flowchartcharter

        root = Path(flowchartcharter.__file__).resolve().parent
    except ImportError:
        root = Path(__file__).resolve().parent

    targets = sorted(str(p) for p in root.glob("*.py"))
    checks = [
        [sys.executable, "-m", "pycodestyle", "--max-line-length=100", *targets],
        [sys.executable, "-m", "pyflakes", *targets],
        [sys.executable, "-m", "compileall", "-q", str(root)],
    ]
    failed = False
    for cmd in checks:
        print("+", " ".join(cmd[:5]), "...")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            failed = True
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    audit_main()
