#!/usr/bin/env python3
"""v2.6 Earned Rhythm — teacher grades evidence, not the maker."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["FCC_HARNESS_PERSIST"] = "0"
os.environ.pop("FCC_ALLOW_FORCE_QUALITY", None)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    EvidenceBundle,
    FlowChartCharterSystem,
    ForceQualityForbidden,
    HarnessKernel,
    __version__,
    build_rhythm_audit,
    collect_evidence,
    earned_quality,
    independent_audit,
)
from flowchartcharter.agents import WorkerNode  # noqa: E402
from flowchartcharter.executive import RhythmValidatorAgent  # noqa: E402


GOOD_PR = {
    "owner": "acme-corp",
    "repo": "secops-service",
    "title": "earned-rhythm",
    "body": "probe",
    "head": "fcc/rhythm",
    "base": "main",
    "diff": "--- a/x\n+++ b/x\n",
    "draft": True,
}


def test_version() -> None:
    assert __version__[0] in "123", __version__
    print("OK version", __version__)


def test_v1_claimed_quality_ignored() -> None:
    result = {
        "ok": True,
        "quality": 0.99,
        "gate": {"valid": False, "quality": 0.99},
        "blocked": False,
        "dry_run": True,
    }
    audit = independent_audit(
        result=result,
        charter_id="lie",
        implementor_role="Key Player",
        auditor_role="Audit Manager",
    )
    assert audit.passed is False, audit
    assert audit.quality < 0.90, audit.quality
    assert "schema_or_gate_fail" in audit.blocking_issues
    print("OK V1 claimed 0.99 + schema fail → fail", audit.quality)


def test_v2_maker_cannot_be_auditor() -> None:
    result = {
        "ok": True,
        "quality": 0.99,
        "gate": {"valid": True},
        "blocked": False,
        "dry_run": True,
    }
    audit = independent_audit(
        result=result,
        charter_id="self",
        implementor_role="Audit Manager",
        auditor_role="Audit Manager",
    )
    assert "maker_checker_violation" in audit.blocking_issues
    assert audit.passed is False
    print("OK V2 self-audit cannot pass")


def test_v3_force_quality_banned() -> None:
    sys_ = FlowChartCharterSystem(seed=26)
    try:
        sys_.execute_charter("cheat", force_quality=0.99)
    except ForceQualityForbidden as exc:
        assert "banned" in str(exc)
        print("OK V3 force_quality banned")
        return
    raise AssertionError("force_quality should have raised")


def test_v4_learning_loop_source() -> None:
    src = (
        ROOT / "loop-engineering" / "Ops" / "run-learning-loop.py"
    ).read_text()
    assert "force_quality" not in src
    print("OK V4 learning loop has no force_quality")


def test_v5_unearned_done_rejected() -> None:
    k = HarnessKernel()
    k.audits.append(
        {
            "type": "RhythmAudit",
            "passed": True,
            "quality": 0.99,
            "earned": False,
        }
    )
    claim = k.claim_done(True, required=1)
    assert claim["done"] is False
    assert claim["rejected"] is True
    print("OK V5 unearned I-passed rejected")


def test_v6_earned_dry_run_passes() -> None:
    k = HarnessKernel()
    worker = WorkerNode("R6", "Release_Operator", {"github_pr": 1.0})
    out = k.run_action(
        "ActionUnit_GitHubPR", worker, GOOD_PR, unit_id="U_ER"
    )
    rhythm = out.get("rhythm_audit") or {}
    assert rhythm.get("earned") is True
    assert rhythm.get("quality") == 0.90
    assert rhythm.get("passed") is True
    claim = k.claim_done(True, required=1)
    assert claim["done"] is True
    print("OK V6 earned dry-run 0.90 + done")


def test_v7_validator_ignores_handed_score() -> None:
    v = RhythmValidatorAgent()
    audit = v.audit(
        "handed-lie",
        marker="gate",
        quality=0.99,
        schema_ok=False,
    )
    assert audit.passed is False
    assert audit.quality < 0.90
    print("OK V7 validator ignores handed 0.99")


def test_v8_formula_and_retrieval() -> None:
    ev = EvidenceBundle(
        schema_ok=True,
        not_blocked=True,
        secrets_clean=True,
        budget_ok=True,
        maker_checker_ok=True,
        halted=False,
        dry_run=True,
        claimed_quality=0.99,
    )
    assert earned_quality(ev) == 0.90
    ev2 = collect_evidence({"ok": True, "quality": 0.99, "halted": True})
    assert earned_quality(ev2) == 0.0
    sys_ = FlowChartCharterSystem(seed=27)
    snap = sys_.execute_charter(
        "earned retrieve",
        payload={"query": "what is FlowChartCharter"},
    )
    hit = snap.get("retrieval") or {}
    rhythm = hit.get("rhythm_audit") or {}
    assert hit.get("claimed_graphrag") is False
    assert rhythm.get("earned") is True
    assert rhythm.get("quality") != 0.92
    print("OK V8 formula + retrieval earned", rhythm.get("quality"))


def test_build_compat() -> None:
    unit = type("U", (), {"id": "U1", "unit_kind": "action"})()
    audit = build_rhythm_audit(
        unit=unit,
        result={"ok": False, "blocked": True, "quality": 0.99, "dry_run": True},
        implementor_role="Key Player",
    )
    assert audit.passed is False
    print("OK build_rhythm_audit compat")


def main() -> None:
    test_version()
    test_v1_claimed_quality_ignored()
    test_v2_maker_cannot_be_auditor()
    test_v3_force_quality_banned()
    test_v4_learning_loop_source()
    test_v5_unearned_done_rejected()
    test_v6_earned_dry_run_passes()
    test_v7_validator_ignores_handed_score()
    test_v8_formula_and_retrieval()
    test_build_compat()
    print("ALL v2.6 EARNED RHYTHM TESTS PASSED")


if __name__ == "__main__":
    main()
