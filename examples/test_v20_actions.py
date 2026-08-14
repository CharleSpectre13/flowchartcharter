"""v2.0 Hands of the Corporation — ActionUnit + CharterHub tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    ActionUnit_GitHubPR,
    ActionUnit_SlackWebhook,
    Agent,
    ENTANGLEMENT_SCHEMA_PENALTY,
    create_action_unit,
    redact_secrets,
    security_audit_action_result,
    __version__,
)
from flowchartcharter.playbook_compiler import (  # noqa: E402
    compile_playbook,
    run_compiled_playbook,
)
from flowchartcharter.system import FlowChartCharterSystem  # noqa: E402


def test_version() -> None:
    assert __version__ >= "2.0.0", __version__


def test_redact_secrets() -> None:
    blob = {
        "Authorization": "Bearer ghp_abcdefghijklmnopqrstuv",
        "text": "hello",
        "nested": {"api_key": "xoxb-1234567890-secret"},
        "url": "https://hooks.slack.com/services/T00/B00/XXXSECRET",
    }
    clean = redact_secrets(blob)
    s = json.dumps(clean)
    assert "ghp_" not in s
    assert "xoxb-" not in s
    assert "hooks.slack.com/services" not in s or "REDACTED" in s
    assert clean["text"] == "hello"
    assert clean["Authorization"] == "***REDACTED***"


def test_slack_schema_blocks_http() -> None:
    unit = ActionUnit_SlackWebhook(dry_run=False)
    agent = Agent("Ops-1", "Release_Operator")
    before = agent.entanglement_errors
    # Missing required text → blocked
    bad = unit.execute({"channel": "#secops"}, agent=agent)
    assert bad.blocked is True
    assert bad.ok is False
    assert bad.entanglement_delta >= ENTANGLEMENT_SCHEMA_PENALTY
    assert agent.entanglement_errors >= before + ENTANGLEMENT_SCHEMA_PENALTY
    audit = security_audit_action_result(bad)
    assert audit["passed"] is True

    # Valid + dry_run
    unit.dry_run = True
    good = unit.execute({"text": "SecOps patch ready for review"}, agent=agent)
    assert good.blocked is False
    assert good.ok is True
    assert good.dry_run is True
    assert good.entanglement_delta == 0
    assert "text" in good.redacted_request


def test_github_schema_and_hallucination() -> None:
    unit = ActionUnit_GitHubPR(dry_run=True)
    agent = Agent("Rel-1", "Release_Operator")
    # Hallucinated empty/short diff blocked
    bad = unit.execute(
        {
            "owner": "acme",
            "repo": "svc",
            "title": "fix",
            "head": "feat/x",
            "base": "main",
            "diff": "x",
        },
        agent=agent,
    )
    assert bad.blocked is True
    assert bad.entanglement_delta >= ENTANGLEMENT_SCHEMA_PENALTY

    # Token in diff blocked
    bad2 = unit.execute(
        {
            "owner": "acme",
            "repo": "svc",
            "title": "fix",
            "head": "feat/x",
            "base": "main",
            "diff": "token ghp_abcdefghijklmnopqrstuvwxyz12 in patch",
        },
        agent=agent,
    )
    assert bad2.blocked is True

    ok = unit.execute(
        {
            "owner": "acme",
            "repo": "svc",
            "title": "secops patch",
            "head": "fcc/patch",
            "base": "main",
            "diff": (
                "--- a/a.py\n+++ b/a.py\n@@ -1 +1,2 @@\n"
                " # secure\n+def ok():\n+    return 1\n"
            ),
        },
        agent=agent,
    )
    assert ok.blocked is False
    assert ok.ok is True
    tel = json.dumps(ok.to_telemetry())
    assert "ghp_" not in tel


def test_factory_registry() -> None:
    a = create_action_unit("ActionUnit_SlackWebhook", unit_id="U_Slack")
    assert isinstance(a, ActionUnit_SlackWebhook)
    b = create_action_unit("github_pr")
    assert isinstance(b, ActionUnit_GitHubPR)


def test_compile_secops_v2_playbook() -> None:
    path = ROOT / "library" / "secops_auto_patch_v2.yaml"
    pb = compile_playbook(path)
    assert pb.playbook_name.startswith("SecOps")
    kinds = {u.id: u.unit_kind for u in pb.flow_units}
    assert kinds["U2_Swarm_Scan"] == "swarm"
    assert kinds["U4_Open_GitHub_PR"] == "action"
    assert kinds["U5_Slack_Notify"] == "action"
    pr = pb.unit_by_id("U4_Open_GitHub_PR")
    assert pr is not None
    assert pr.action_type == "ActionUnit_GitHubPR"


def test_run_secops_playbook_end_to_end() -> None:
    path = ROOT / "library" / "secops_auto_patch_v2.yaml"
    system = FlowChartCharterSystem(seed=21)
    meta = system.load_playbook(path)
    assert meta["playbook_name"]
    result = run_compiled_playbook(
        system,
        "Scan auth module and open PR for CVE fixes",
    )
    assert result["units_total"] >= 5
    kinds = [r.get("unit_kind") for r in result["unit_results"]]
    assert "swarm" in kinds
    assert "action" in kinds
    actions = [r for r in result["unit_results"] if r.get("unit_kind") == "action"]
    assert actions
    for a in actions:
        # schema-valid dry-run should not be blocked
        assert a.get("blocked") is False or a.get("ok") is True
        blob = json.dumps(a.get("action") or {})
        assert "ghp_" not in blob
        assert "xoxb-" not in blob
        assert "hooks.slack.com/services/" not in blob or "REDACTED" in blob


def test_fear_on_action_via_system() -> None:
    system = FlowChartCharterSystem(seed=3)
    agent = next(a for a in system.roster if not isinstance(a, type(system.boss)))
    from flowchartcharter.agents import BossAgent

    agent = next(a for a in system.roster if not isinstance(a, BossAgent))
    unit = ActionUnit_SlackWebhook(dry_run=True)
    before = agent.entanglement_errors
    unit.execute({"text": ""}, agent=agent)  # invalid
    assert agent.entanglement_errors > before


def main() -> None:
    test_version()
    test_redact_secrets()
    test_slack_schema_blocks_http()
    test_github_schema_and_hallucination()
    test_factory_registry()
    test_compile_secops_v2_playbook()
    test_run_secops_playbook_end_to_end()
    test_fear_on_action_via_system()
    print("ALL v2.0 ACTION TESTS PASSED")
    print(f"flowchartcharter {__version__}")


if __name__ == "__main__":
    main()
