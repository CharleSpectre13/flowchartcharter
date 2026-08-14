"""v2.6 Earned Rhythm — ST-04 maker-checker.

The teacher grades evidence. The maker's quality number is ignored.
Audit Manager is a separate function. It does not read 'I passed'.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .vectors import RhythmAudit

CANONICAL_MARKERS = (
    "start",
    "bind",
    "superstep",
    "gate",
    "loop",
    "handoff",
    "sync",
    "action",
    "coach",
    "swarm",
)

W_SCHEMA = 0.40
W_UNBLOCKED = 0.20
W_SECRETS = 0.15
W_BUDGET = 0.15
W_CHECKER = 0.10
DRY_RUN_CAP = 0.90
DEFAULT_THRESHOLD = 0.90


class RhythmViolationError(Exception):
    """Raised when a unit fails ST-04 exit criteria after remediation cap."""

    def __init__(
        self,
        message: str,
        *,
        audit: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.audit = audit or {}


class ForceQualityForbidden(ValueError):
    """force_quality is banned under Earned Rhythm."""


@dataclass
class EvidenceBundle:
    """Frozen facts the auditor may see. No maker grade."""

    schema_ok: bool = False
    not_blocked: bool = False
    secrets_clean: bool = True
    budget_ok: bool = True
    maker_checker_ok: bool = True
    halted: bool = False
    dry_run: bool = True
    claimed_quality: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_ok": self.schema_ok,
            "not_blocked": self.not_blocked,
            "secrets_clean": self.secrets_clean,
            "budget_ok": self.budget_ok,
            "maker_checker_ok": self.maker_checker_ok,
            "halted": self.halted,
            "dry_run": self.dry_run,
            "claimed_quality_ignored": self.claimed_quality,
        }


def marker_for_unit(unit: Any) -> str:
    """Map unit kind → canonical rhythm marker."""
    kind = str(getattr(unit, "unit_kind", None) or "flow").lower()
    if kind == "action":
        return "action"
    if kind == "swarm" or bool(getattr(unit, "swarm", False)):
        return "swarm"
    uid = str(getattr(unit, "id", "") or "").lower()
    if "validate" in uid or "compliance" in uid or "audit" in uid:
        return "gate"
    if "inventory" in uid or "ingest" in uid:
        return "start"
    return "superstep"


def _as_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def collect_evidence(
    result: Optional[Dict[str, Any]] = None,
    *,
    implementor_role: str = "",
    auditor_role: str = "Audit Manager",
) -> EvidenceBundle:
    """Build evidence. Maker quality fields are stored, never used as Q."""
    result = result or {}
    gate = _as_mapping(result.get("gate"))
    action = _as_mapping(result.get("action"))
    status = str(result.get("status") or "")
    err = str(result.get("error") or action.get("error") or "")
    halted = bool(result.get("halted")) or status == "HALTED" or (
        "kill_switch" in err
    )
    blocked = bool(result.get("blocked")) or status.startswith("BLOCKED")
    if halted:
        blocked = True
    schema_fail = (
        gate.get("valid") is False
        or err.startswith("payload_schema_fail")
        or "schema_or_gate_fail" in err
        or "BLOCKED_SCHEMA" in status
    )
    schema_ok = (not schema_fail) and (not halted)
    if gate.get("valid") is True:
        schema_ok = (not halted) and (not schema_fail)
    elif result.get("ok") is True and not blocked and not schema_fail:
        schema_ok = not halted
    secrets_clean = True
    leak_bits = (
        str(result.get("response_summary") or ""),
        err,
        str(action.get("error") or ""),
        str(action.get("response_summary") or ""),
    )
    if any("secret_leak" in x or "REDACTED_LEAK" in x for x in leak_bits):
        secrets_clean = False
    budget_ok = not bool(
        result.get("budget_halt") or err == "tenant_cfo_ceiling"
    )
    impl = (implementor_role or "").lower()
    aud = (auditor_role or "Audit Manager").lower()
    maker_ok = True
    if impl and aud and "audit" in impl and impl == aud:
        maker_ok = False
    dry = bool(
        result.get("dry_run")
        or result.get("mock")
        or status == "SUCCESS_DRY_RUN"
        or action.get("dry_run")
    )
    claimed = None
    for src in (result, gate, action):
        if isinstance(src, dict) and "quality" in src:
            try:
                claimed = float(src["quality"])
                break
            except (TypeError, ValueError):
                pass
    return EvidenceBundle(
        schema_ok=bool(schema_ok),
        not_blocked=not blocked,
        secrets_clean=secrets_clean,
        budget_ok=budget_ok,
        maker_checker_ok=maker_ok,
        halted=halted,
        dry_run=dry,
        claimed_quality=claimed,
    )


def earned_quality(evidence: EvidenceBundle) -> float:
    """Deterministic Q. Claimed maker quality is not an input."""
    if evidence.halted:
        return 0.0
    q = (
        W_SCHEMA * float(evidence.schema_ok)
        + W_UNBLOCKED * float(evidence.not_blocked)
        + W_SECRETS * float(evidence.secrets_clean)
        + W_BUDGET * float(evidence.budget_ok)
        + W_CHECKER * float(evidence.maker_checker_ok)
    )
    if evidence.dry_run:
        q = min(q, DRY_RUN_CAP)
    return round(q, 4)


def issues_from_evidence(evidence: EvidenceBundle) -> List[str]:
    issues: List[str] = []
    if evidence.halted:
        issues.append("kill_switch_halted")
    if not evidence.schema_ok:
        issues.append("schema_or_gate_fail")
    if not evidence.not_blocked:
        issues.append("action_blocked")
    if not evidence.secrets_clean:
        issues.append("secret_leak")
    if not evidence.budget_ok:
        issues.append("budget_halt")
    if not evidence.maker_checker_ok:
        issues.append("maker_checker_violation")
    return issues


def independent_audit(
    *,
    unit: Any = None,
    result: Optional[Dict[str, Any]] = None,
    evidence: Optional[EvidenceBundle] = None,
    charter_id: str = "",
    threshold: float = DEFAULT_THRESHOLD,
    remediation_loops: int = 0,
    implementor_role: str = "",
    auditor_role: str = "Audit Manager",
    marker: str = "",
) -> RhythmAudit:
    """Tier B. Sees evidence only. Cannot read the maker's grade."""
    ev = evidence or collect_evidence(
        result,
        implementor_role=implementor_role,
        auditor_role=auditor_role,
    )
    quality = earned_quality(ev)
    issues = issues_from_evidence(ev)
    if result is not None and result.get("ok") is False and not ev.halted:
        if "unit_not_ok" not in issues and not ev.schema_ok:
            issues.append("unit_not_ok")
    passed = quality >= float(threshold) and not issues
    uid = charter_id or str(getattr(unit, "id", "") or "unit")
    return RhythmAudit(
        marker=marker or marker_for_unit(unit),
        charter_id=uid,
        quality=float(quality),
        threshold=float(threshold),
        passed=passed,
        remediation_loops=int(remediation_loops),
        blocking_issues=tuple(issues),
    )


def quality_from_result(result: Dict[str, Any]) -> float:
    """Backward-compatible name. Now earned, not a gift."""
    return earned_quality(collect_evidence(result))


def build_rhythm_audit(
    *,
    unit: Any,
    result: Dict[str, Any],
    charter_id: str = "",
    threshold: float = DEFAULT_THRESHOLD,
    remediation_loops: int = 0,
    implementor_role: str = "",
    auditor_role: str = "Audit Manager",
) -> RhythmAudit:
    """ST-04 RhythmAudit from evidence. Maker quality is ignored."""
    return independent_audit(
        unit=unit,
        result=result,
        charter_id=charter_id,
        threshold=threshold,
        remediation_loops=remediation_loops,
        implementor_role=implementor_role,
        auditor_role=auditor_role,
    )


def enforce_rhythm_or_raise(
    audit: RhythmAudit,
    *,
    max_remediation: int = 3,
    hard_stop: bool = False,
) -> Dict[str, Any]:
    """Return audit dict; raise if failed and past remediation cap + hard_stop."""
    blob = _blob(audit)
    if audit.passed:
        return blob
    if hard_stop and audit.remediation_loops >= max_remediation:
        raise RhythmViolationError(
            f"Rhythm gate failed at marker={audit.marker} "
            f"quality={audit.quality:.3f} < {audit.threshold} "
            f"issues={list(audit.blocking_issues)}",
            audit=blob,
        )
    return blob


def attach_rhythm(
    result: Dict[str, Any],
    audit: RhythmAudit,
) -> Dict[str, Any]:
    """Copy result with earned rhythm_audit."""
    out = dict(result)
    blob = _blob(audit, result=result)
    out["rhythm_audit"] = blob
    out["rhythm_passed"] = audit.passed
    return out


def _blob(
    audit: RhythmAudit,
    *,
    result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    blob = audit.to_dict()
    blob["earned"] = True
    if result is not None:
        blob["evidence"] = collect_evidence(result).to_dict()
    return blob
