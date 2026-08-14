"""Live harness / Charter audit probes.

Maker-checker: this module inspects evidence. It does not assign a 1-10 gift.
loop-engineer + rhythm-marker-validator.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .retrieval_port import RetrievalHit, RetrievalResult


def run_system_audit(system: Any) -> Dict[str, Any]:
    """Probe halt, retrieve, cite, episode, QFS reduce. Fail-closed."""
    probes = [
        _probe_halt(system),
        _probe_simple_muscle(system),
        _probe_honesty(system),
        _probe_citation(system),
        _probe_episode(system),
        _probe_qfs_reduce(system),
        _probe_rhythm_independent(),
        _probe_stranger(system),
        _probe_sandbox_deny(system),
    ]
    failed = [p["name"] for p in probes if not p.get("ok")]
    return {
        "ok": not failed,
        "failed": failed,
        "probes": probes,
        "claimed_graphrag": False,
        "auditor": "Audit Manager",
        "implementor": "System Audit Tool",
    }


def _probe_halt(system: Any) -> Dict[str, Any]:
    h = system.harness
    h.halt("audit_probe")
    blocked = not h.kill.armed
    snap = system.execute_charter("AuditHaltProbe")
    refused = bool(snap.get("halted"))
    h.arm()
    return {
        "name": "halt_roundtrip",
        "ok": blocked and refused and h.kill.armed,
        "evidence": {"blocked": blocked, "refused": refused, "rearmed": h.kill.armed},
    }


def _probe_simple_muscle(system: Any) -> Dict[str, Any]:
    hit = system.harness.retrieve("what is FlowChartCharter", mode="simple")
    ok = hit.backend == "muscle_memory" and hit.claimed_graphrag is False
    return {
        "name": "simple_muscle",
        "ok": ok,
        "evidence": {"backend": hit.backend, "claimed_graphrag": hit.claimed_graphrag},
    }


def _probe_honesty(system: Any) -> Dict[str, Any]:
    hit = system.harness.retrieve("DeltaNotebook", mode="lazy")
    ok = hit.claimed_graphrag is False
    return {
        "name": "retrieval_honesty",
        "ok": ok,
        "evidence": {"backend": hit.backend, "claimed_graphrag": hit.claimed_graphrag},
    }


def _probe_citation(system: Any) -> Dict[str, Any]:
    fake = RetrievalResult(
        backend="fcc_lazy",
        mode="lazy",
        hits=[RetrievalHit(id="x", title="bare", snippet="n", score=1.0, source="")],
    )
    stamped = system.harness.retrieval._stamp_rhythm(fake)
    issues = (stamped.rhythm_audit or {}).get("blocking_issues") or []
    ok = "ungrounded_hit" in issues
    return {
        "name": "citation_law",
        "ok": ok,
        "evidence": {"issues": list(issues)},
    }


def _probe_episode(system: Any) -> Dict[str, Any]:
    before = len(system.knowledge.data.get("text_units") or [])
    snap = system.execute_charter("AuditEpisodeProbe")
    after = len(system.knowledge.data.get("text_units") or [])
    ep = snap.get("episode") or {}
    ok = after > before and ep.get("episode") is True and not ep.get("claimed_graphrag")
    return {
        "name": "episode_bind",
        "ok": ok,
        "evidence": {
            "before": before,
            "after": after,
            "rebuild": system.knowledge.data.get("full_rebuild"),
        },
    }


def _probe_qfs_reduce(system: Any) -> Dict[str, Any]:
    system.ingest_memory(
        "AlphaRiver irrigation fails when silt blocks the intake.",
        source_id="audit-theme-a",
    )
    system.ingest_memory(
        "BetaHarbor shipping delays when fog closes the channel.",
        source_id="audit-theme-b",
    )
    pack = system.knowledge.qfs_search("AlphaRiver")
    bags = {p.get("bag") for p in (pack.get("partials") or [])}
    ok = "audit-theme-a" in bags and "audit-theme-b" not in bags
    return {
        "name": "qfs_reduce",
        "ok": ok,
        "evidence": {
            "bags": sorted(str(b) for b in bags),
            "backend": pack.get("backend"),
        },
    }


def _probe_rhythm_independent() -> Dict[str, Any]:
    from .rhythm_gate import independent_audit

    good = independent_audit(
        result={"ok": True, "blocked": False, "dry_run": True, "gate": {"valid": True}},
        charter_id="audit-rhythm",
        implementor_role="Key Player",
        auditor_role="Audit Manager",
        marker="gate",
    )
    same = independent_audit(
        result={"ok": True, "blocked": False, "dry_run": True, "gate": {"valid": True}},
        charter_id="audit-rhythm-self",
        implementor_role="Audit Manager",
        auditor_role="Audit Manager",
        marker="gate",
    )
    ok = bool(good.passed) and not bool(same.passed)
    return {
        "name": "rhythm_independent",
        "ok": ok,
        "evidence": {"split_pass": good.passed, "self_pass": same.passed},
    }


def _probe_stranger(system: Any) -> Dict[str, Any]:
    from .stranger_receipt import verify_chain

    a = system.issue_stranger_receipt()
    b = system.issue_stranger_receipt()
    ok = verify_chain([a, b]) and a.get("claimed_graphrag") is False
    return {
        "name": "stranger_receipt",
        "ok": ok,
        "evidence": {"hash": a.get("hash", "")[:12], "chained": True},
    }


def _probe_sandbox_deny(system: Any) -> Dict[str, Any]:
    refuse = system.harness.sandbox.allow("shell", halted=False)
    ok = refuse == "action_denied_by_default"
    return {
        "name": "sandbox_deny",
        "ok": ok,
        "evidence": {"refuse": refuse, "policy_not_kernel": True},
    }


def format_audit_report(receipt: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# CXR — Live system audit",
        "",
        f"**ok:** {receipt.get('ok')}",
        f"**failed:** {', '.join(receipt.get('failed') or []) or 'none'}",
        "",
    ]
    for probe in receipt.get("probes") or []:
        mark = "PASS" if probe.get("ok") else "FAIL"
        lines.append(f"- {probe.get('name')}: {mark}")
    lines.append("")
    lines.append("Auditor ≠ implementor. No 1-10 gift from this tool.")
    return "\n".join(lines)
