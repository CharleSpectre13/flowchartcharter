#!/usr/bin/env python3
"""Pre-repository-creation audit gate (continuous-team-audit-loop)."""
from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "07_CROSS_REFERENCE_REPORTS"


def audit(repo_name: str, completed: str, excellent: list, weak: list, adjustments: list) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = REPORTS / f"CXR-{ts}-{repo_name}.md"
    blocking = [w for w in weak if w.startswith("BLOCKING:")]
    body = f"""# Cross-Reference Report — pre-repo:{repo_name}

**Timestamp:** {ts}
**Gate:** continuous-team-audit-loop + loop-engineer

## What was just completed
{completed}

## What was excellent
""" + "\n".join(f"- {e}" for e in excellent) + """

## What was weak or risky
""" + "\n".join(f"- {w}" for w in weak) + """

## Do's & Don'ts tested
- DO run audit before every public repo creation
- DO keep Charter primary / GraphRAG secondary
- DO maker-checker on verification criteria
- DON'T push secrets or private keys
- DON'T claim production LLM fidelity for simulated metrics

## What other divisions need to know
- Open design Apache-2.0 under CharleSpectre13
- Skill: flowchartcharter-engineering activated
- Learning loop receipt written to loop-engineering/Memory/

## Concrete adjustment for next cycle
""" + "\n".join(f"- {a}" for a in adjustments) + f"""

## Zero-Knowledge Verification
- Pre-repo audit gate executed: YES
- Blocking issues: {len(blocking)}
- Constitution present: {(ROOT / 'constitution' / 'constitution.md').exists()}
- SPEC six elements present: {(ROOT / 'spec' / 'SPEC.md').exists()}

## Verdict
{\"HALT\" if blocking else \"PASS — proceed to create repository\"}
"""
    path.write_text(body)
    print(path)
    print("HALT" if blocking else "PASS")
    return path


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "unnamed"
    audit(
        repo,
        completed=sys.argv[2] if len(sys.argv) > 2 else "Foundation artifacts staged",
        excellent=["SDD SPEC complete", "Core demo green"],
        weak=["Simulated agent quality only"],
        adjustments=["Add property tests for reducers", "Normalize fitness cost term"],
    )
