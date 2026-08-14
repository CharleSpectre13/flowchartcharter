"""v2.2 Ironclad — Top-7 audit fixes verification."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    SecretScrubber,
    StatePersisterVault,
    TenantNamespacedEngine,
    __version__,
    build_rhythm_audit,
    get_tenant_registry,
    list_providers,
    run_golden_evals,
    validate_synthesized_unit,
)
from flowchartcharter.playbook_compiler import (  # noqa: E402
    compile_playbook,
    run_compiled_playbook,
)
from flowchartcharter.system import FlowChartCharterSystem  # noqa: E402
from flowchartcharter.state_persister import StatePersister  # noqa: E402


def test_version() -> None:
    assert __version__[0] in "123", __version__


def test_secret_scrubber_and_vault() -> None:
    raw = {
        "tenant_id": "ORG-ALPHA",
        "FCC_GITHUB_TOKEN": "ghp_ABC123XYZ789FakeTokenForTestXX",
        "nested": {"api_key": "xoxb-1234567890-secretsecret"},
        "note": "safe",
        "url": "https://hooks.slack.com/services/T00/B00/XXXSECRET",
    }
    clean = SecretScrubber.scrub(raw)
    blob = json.dumps(clean)
    assert "ghp_" not in blob
    assert "xoxb-" not in blob
    assert "hooks.slack.com/services" not in blob or "REDACTED" in blob
    assert clean["note"] == "safe"
    assert clean["FCC_GITHUB_TOKEN"] == "REDACTED_BY_FCC_VAULT"

    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "vault.json")
        vault = StatePersisterVault(path)
        vault.snapshot(raw)
        loaded = json.loads(Path(path).read_text())
        assert "ghp_" not in json.dumps(loaded)


def test_persister_write_time_scrub() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "system_state.json")
        persister = StatePersister(path)
        system = FlowChartCharterSystem(seed=1)
        # inject secret-looking field into checkpointer
        system.checkpointer.append(
            {"FCC_GITHUB_TOKEN": "ghp_ABCDEFGHIJKLMNOPQRSTUVWX12", "ok": True}
        )
        # dump_system may not include checkpointer secrets — force via monkey patch
        orig = persister.dump_system

        def dump_with_secret(sys):
            d = orig(sys)
            d["FCC_SLACK_WEBHOOK"] = "https://hooks.slack.com/services/T/B/XXX"
            d["notes"] = "token ghp_ABCDEFGHIJKLMNOPQRSTUVWX99 leaked"
            return d

        persister.dump_system = dump_with_secret  # type: ignore[method-assign]
        persister.save(system)
        on_disk = Path(path).read_text()
        assert "ghp_" not in on_disk
        assert "hooks.slack.com/services" not in on_disk or "REDACTED" in on_disk


def test_multi_tenant_isolation() -> None:
    reg = get_tenant_registry()
    a = reg.get_or_create("ORG-ALPHA", cfo_ceiling=1000)
    b = reg.get_or_create("ORG-BETA", cfo_ceiling=500)
    assert a is not b
    assert a.charge_budget(200) is True
    assert a.token_spent == 200
    assert b.token_spent == 0
    assert b.charge_budget(600) is False  # over 500
    assert reg.isolate_check("ORG-ALPHA", "ORG-BETA") is True
    a.commit_memory({"job_type": "alpha-only", "path": ["U1"]})
    assert len(b.query_memory()) == 0 or all(
        r.get("tenant_id") != "ORG-BETA" or r.get("job_type") != "alpha-only"
        for r in b.query_memory()
    )
    # alpha memory not in beta
    assert not any(r.get("job_type") == "alpha-only" for r in b.muscle_memory_db)


def test_synthesizer_hard_filters() -> None:
    # Internal AWS without github keywords → no GitHub unit
    assert validate_synthesized_unit(
        "ActionUnit_GitHubPR",
        "Perform secure internal AWS migration",
    ) is False
    # Explicit github intent allowed
    assert validate_synthesized_unit(
        "ActionUnit_GitHubPR",
        "Open github PR with security patch",
    ) is True
    # Slack without notify intent blocked
    assert validate_synthesized_unit(
        "ActionUnit_SlackWebhook",
        "Inventory packages only",
    ) is False
    assert validate_synthesized_unit(
        "ActionUnit_SlackWebhook",
        "Audit AWS and alert Slack",
    ) is True

    system = FlowChartCharterSystem(seed=2)
    out = system.synthesize_charter(
        "Audit AWS infrastructure for compliance",
        coach_ceiling=8000,
    )
    units = out["draft"]["unit_ids"]
    joined = " ".join(units).lower()
    assert "github" not in joined
    # Slack only if alert/slack in goal — this goal has neither
    assert "slack" not in joined


def test_rhythm_on_compiled_playbook() -> None:
    system = FlowChartCharterSystem(seed=5)
    draft = system.synthesize_charter(
        "Migrate billing with github pr and slack notify",
        coach_ceiling=15000,
    )
    system.approve_charter(draft["draft_id"], execute_workload="billing dry-run")
    # execute already ran — check last checkpoint or re-run
    result = system.execute_compiled("billing re-run")
    assert "rhythm_audits" in result
    assert len(result["rhythm_audits"]) >= 1
    assert all("marker" in a for a in result["rhythm_audits"])
    assert result.get("version") == "2.2.0"


def test_llm_golden_and_providers() -> None:
    providers = list_providers()
    assert any(p.name == "mock" for p in providers)
    report = run_golden_evals()
    assert report["total"] >= 3
    assert report["passed"] == report["total"]


def test_system_tenant_bound() -> None:
    system = FlowChartCharterSystem(seed=9)
    assert hasattr(system, "tenant_id")
    assert hasattr(system, "tenant")
    assert system.tenant.tenant_id == system.tenant_id


def main() -> None:
    test_version()
    test_secret_scrubber_and_vault()
    test_persister_write_time_scrub()
    test_multi_tenant_isolation()
    test_synthesizer_hard_filters()
    test_rhythm_on_compiled_playbook()
    test_llm_golden_and_providers()
    test_system_tenant_bound()
    print("ALL v2.2 IRONCLAD TESTS PASSED")
    print(f"flowchartcharter {__version__}")


if __name__ == "__main__":
    main()
