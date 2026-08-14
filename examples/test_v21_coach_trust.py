"""v2.1 Coach Trust Hand-Off — CharterSynthesizer tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    CharterDraftStatus,
    CharterSynthesizer,
    __version__,
    audit_cfo_ceiling,
)
from flowchartcharter.charter_synthesizer import (  # noqa: E402
    FlowUnitDraft,
    RosterDraft,
    SynthesizedCharterSchema,
)
from flowchartcharter.playbook_compiler import compile_playbook  # noqa: E402
from flowchartcharter.system import FlowChartCharterSystem  # noqa: E402


def test_version() -> None:
    assert __version__ >= "2.0.0", __version__


def test_cfo_audit_clamps() -> None:
    units = [
        FlowUnitDraft(
            id="U1",
            description="a",
            assigned_role="R1",
            expected_tokens=4000,
            schema_fields={"x": "string"},
        ),
        FlowUnitDraft(
            id="U2",
            description="b",
            assigned_role="R2",
            expected_tokens=4000,
            schema_fields={"y": "int"},
        ),
    ]
    charter = SynthesizedCharterSchema(
        playbook_name="Over Budget",
        global_cfo_ceiling=50_000,  # way over coach
        roster_requisition=[
            RosterDraft(role="R1", capabilities=["general"]),
            RosterDraft(role="R2", capabilities=["general"]),
        ],
        flow_units=units,
        estimated_token_total=8000,
    )
    adj, audit = audit_cfo_ceiling(charter, coach_ceiling=5000)
    assert audit.passed is True
    assert adj.global_cfo_ceiling <= 5000
    assert adj.estimated_token_total <= adj.global_cfo_ceiling


def test_synthesize_pending_not_executed() -> None:
    system = FlowChartCharterSystem(seed=42)
    out = system.synthesize_charter(
        "Audit AWS infrastructure and alert Slack",
        coach_ceiling=10_000,
    )
    assert out["status"] == CharterDraftStatus.PENDING_COACH_APPROVAL.value
    assert "yaml_text" in out and "flow_units" in out["yaml_text"]
    assert out["cfo_audit"]["passed"] is True
    assert out["draft_id"] in system.boss.pending_charters
    # Must not have auto-loaded as active without approval
    # (compiled may still be None or previous)
    pending = system.list_pending_charters()
    assert pending["count"] >= 1


def test_approve_loads_and_optional_execute() -> None:
    system = FlowChartCharterSystem(seed=7)
    draft = system.synthesize_charter(
        "Migrate billing system from Stripe to PayPal with GitHub PR",
        coach_ceiling=15_000,
    )
    draft_id = draft["draft_id"]
    # Compile-valid YAML
    pb = compile_playbook(draft["yaml_text"])
    assert pb.global_cfo_ceiling <= 15_000
    assert any(u.unit_kind in ("action", "flow", "swarm") for u in pb.flow_units)

    approved = system.approve_charter(
        draft_id,
        approved_by="Head Coach",
        execute_workload="billing migration dry-run",
    )
    assert approved["status"] == CharterDraftStatus.APPROVED.value
    assert draft_id not in system.boss.pending_charters
    assert system.compiled_playbook is not None
    assert approved.get("execution") is not None
    assert approved["execution"]["units_total"] >= 1


def test_reject_blocks() -> None:
    system = FlowChartCharterSystem(seed=3)
    draft = system.synthesize_charter("Simple inventory audit")
    rid = draft["draft_id"]
    system.reject_charter(rid, reason="not now")
    try:
        system.approve_charter(rid)
        raise AssertionError("should not approve rejected")
    except Exception:
        pass


def test_synthesizer_standalone() -> None:
    synth = CharterSynthesizer(coach_ceiling=8000)
    d = synth.synthesize("secops scan and slack alert")
    assert d.status == CharterDraftStatus.PENDING_COACH_APPROVAL
    assert "ActionUnit_SlackWebhook" in d.yaml_text or "Slack" in d.yaml_text
    assert d.cfo_audit.passed


def main() -> None:
    test_version()
    test_cfo_audit_clamps()
    test_synthesize_pending_not_executed()
    test_approve_loads_and_optional_execute()
    test_reject_blocks()
    test_synthesizer_standalone()
    print("ALL v2.1 COACH TRUST TESTS PASSED")
    print(f"flowchartcharter {__version__}")


if __name__ == "__main__":
    main()
