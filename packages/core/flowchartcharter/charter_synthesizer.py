"""v2.1 Coach Trust Hand-Off — Autonomous Charter Synthesis.

Boss Agent turns a high-level enterprise goal into a Charterfile YAML draft
by consulting Muscle-Memory for proven Flow Units, then holds the draft in
``PENDING_COACH_APPROVAL`` until the Head Coach 1-click approves.

Iron rules:
  - Synthesized YAML always respects global CFO_Ceiling (logic audit).
  - Drafts never execute until ``approve_charter(draft_id)``.
  - LLM path uses a strict Pydantic output schema; mock path is deterministic.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml
from pydantic import BaseModel, Field, field_validator

from .muscle_memory import (
    ExecutionMemoryRecord,
    MuscleMemoryVectorDB,
    encode_state,
)
from .playbook_compiler import (
    CompiledPlaybook,
    PlaybookCompileError,
    compile_playbook,
)
from .vectors import RhythmAudit

# ---------------------------------------------------------------------------
# Status machine
# ---------------------------------------------------------------------------


class CharterDraftStatus(str, Enum):
    PENDING_COACH_APPROVAL = "PENDING_COACH_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"


# ---------------------------------------------------------------------------
# LLM / synthesizer Pydantic contracts
# ---------------------------------------------------------------------------


class FlowUnitDraft(BaseModel):
    """One unit inside a synthesized charter (schema-locked)."""

    id: str = Field(..., min_length=1, max_length=80)
    description: str = Field(..., min_length=1, max_length=500)
    assigned_role: str = Field(..., min_length=1, max_length=80)
    expected_tokens: int = Field(..., ge=50, le=50_000)
    expected_latency_ms: float = Field(default=300.0, ge=1.0, le=600_000.0)
    unit_kind: str = Field(default="flow")  # flow | swarm | action
    action: Optional[str] = None
    swarm: bool = False
    swarm_max_workers: int = Field(default=8, ge=1, le=64)
    schema_fields: Dict[str, str] = Field(default_factory=dict)
    action_config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def safe_id(cls, v: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z_]", "_", v.strip())
        if not cleaned:
            raise ValueError("unit id empty")
        if cleaned[0].isdigit():
            cleaned = f"U_{cleaned}"
        return cleaned

    @field_validator("unit_kind")
    @classmethod
    def kind_ok(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("flow", "swarm", "action"):
            raise ValueError("unit_kind must be flow|swarm|action")
        return v


class RosterDraft(BaseModel):
    role: str = Field(..., min_length=1, max_length=80)
    capabilities: List[str] = Field(default_factory=list)


class SynthesizedCharterSchema(BaseModel):
    """Strict LLM output schema for Charter synthesis."""

    playbook_name: str = Field(..., min_length=1, max_length=160)
    version: str = Field(default="2.1.0", max_length=32)
    global_cfo_ceiling: int = Field(..., ge=100, le=5_000_000)
    roster_requisition: List[RosterDraft] = Field(..., min_length=1)
    flow_units: List[FlowUnitDraft] = Field(..., min_length=1, max_length=40)
    rationale: str = Field(default="", max_length=2000)
    muscle_memory_ids: List[str] = Field(default_factory=list)
    estimated_token_total: int = Field(default=0, ge=0)

    @field_validator("playbook_name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        return v.strip() or "Synthesized Playbook"


class CfoCeilingAudit(BaseModel):
    """Logic audit: synthesized plan vs coach ceiling."""

    passed: bool
    coach_ceiling: int
    proposed_ceiling: int
    sum_expected_tokens: int
    adjusted_ceiling: int
    findings: List[str] = Field(default_factory=list)


class CharterDraft(BaseModel):
    """In-memory pending charter awaiting Head Coach 1-click."""

    draft_id: str
    status: CharterDraftStatus = CharterDraftStatus.PENDING_COACH_APPROVAL
    goal: str
    yaml_text: str
    charter: SynthesizedCharterSchema
    cfo_audit: CfoCeilingAudit
    muscle_hits: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    approved_at: Optional[float] = None
    rejected_at: Optional[float] = None
    approved_by: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    rhythm_audit: Dict[str, Any] = Field(default_factory=dict)
    synthesis_source: str = "muscle_heuristic"

    def to_public(self) -> Dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "status": self.status.value,
            "goal": self.goal,
            "yaml_text": self.yaml_text,
            "playbook_name": self.charter.playbook_name,
            "version": self.charter.version,
            "global_cfo_ceiling": self.charter.global_cfo_ceiling,
            "estimated_token_total": self.charter.estimated_token_total,
            "cfo_audit": self.cfo_audit.model_dump(),
            "muscle_hits": self.muscle_hits,
            "muscle_memory_ids": list(self.charter.muscle_memory_ids),
            "unit_ids": [u.id for u in self.charter.flow_units],
            "roster": [r.model_dump() for r in self.charter.roster_requisition],
            "rationale": self.charter.rationale,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "rejected_at": self.rejected_at,
            "approved_by": self.approved_by,
            "rhythm_audit": self.rhythm_audit,
            "has_execution": self.execution_result is not None,
            "synthesis_source": self.synthesis_source,
        }


# ---------------------------------------------------------------------------
# Unit template library (seeded from muscle + domain heuristics)
# ---------------------------------------------------------------------------

_UNIT_LIBRARY: Dict[str, Dict[str, Any]] = {
    "inventory": {
        "id": "U1_Inventory",
        "description": "Inventory assets / surface / dependencies for the goal.",
        "role": "Inventory_Analyst",
        "caps": ["discovery", "json_parsing", "general"],
        "tokens": 800,
        "schema": {
            "assets_found": "list[string]",
            "files": "list[string]",
            "risk_score": "float",
        },
        "tags": ("audit", "migrate", "aws", "inventory", "scan"),
    },
    "swarm_scan": {
        "id": "U2_Swarm_Scan",
        "description": "Parallel swarm scan of inventory items under CFO ceiling.",
        "role": "Threat_Scanner",
        "caps": ["security_audit", "sast", "swarm"],
        "tokens": 2000,
        "kind": "swarm",
        "swarm": True,
        "schema": {
            "files": "list[string]",
            "findings": "list[string]",
            "scanned": "int",
            "failed": "int",
        },
        "tags": ("scan", "audit", "security", "aws", "swarm"),
    },
    "transform": {
        "id": "U3_Transform",
        "description": "Transform / migrate core logic with schema validation.",
        "role": "Migration_Engineer",
        "caps": ["python_ast", "refactoring", "etl"],
        "tokens": 2500,
        "schema": {
            "transformed": "bool",
            "diff": "string",
            "residual_risk": "float",
            "notes": "string",
        },
        "tags": ("migrate", "billing", "stripe", "paypal", "etl"),
    },
    "validate": {
        "id": "U4_Validate",
        "description": "Validate outputs against policy and acceptance gates.",
        "role": "Compliance_Validator",
        "caps": ["policy_check", "validation", "audit"],
        "tokens": 900,
        "schema": {
            "policy_pass": "bool",
            "report_json": "string",
            "executive_summary": "string",
        },
        "tags": ("audit", "validate", "compliance", "billing"),
    },
    "github_pr": {
        "id": "U5_Open_GitHub_PR",
        "description": "ActionUnit_GitHubPR — open PR with validated patch.",
        "role": "Release_Operator",
        "caps": ["github_pr", "change_management"],
        "tokens": 400,
        "kind": "action",
        "action": "ActionUnit_GitHubPR",
        "schema": {
            "owner": "string",
            "repo": "string",
            "title": "string",
            "body": "string",
            "head": "string",
            "base": "string",
            "diff": "string",
            "draft": "bool",
        },
        "action_config": {
            "owner": "acme-corp",
            "repo": "enterprise-service",
            "head": "fcc/auto-synth",
            "base": "main",
            "dry_run": True,
        },
        "tags": ("github", "pr", "patch", "migrate", "code"),
    },
    "slack_alert": {
        "id": "U6_Slack_Alert",
        "description": "ActionUnit_SlackWebhook — notify channel of outcome.",
        "role": "Release_Operator",
        "caps": ["slack_ops", "comms"],
        "tokens": 120,
        "kind": "action",
        "action": "ActionUnit_SlackWebhook",
        "schema": {"text": "string", "channel": "string", "username": "string"},
        "action_config": {
            "text": "FlowChartCharter synthesized run complete.",
            "username": "FCC-Coach",
            "dry_run": True,
        },
        "tags": ("slack", "alert", "notify", "aws", "ops"),
    },
}


def _goal_keywords(goal: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", goal.lower())
    return set(tokens)


# Action units that require explicit goal intent (R6 hard-filters)
_ACTION_UNIT_REQUIREMENTS: Dict[str, set[str]] = {
    "github_pr": {"github", "pr", "pull", "patch", "diff", "repo", "commit"},
    "slack_alert": {"slack", "alert", "notify", "webhook", "channel", "message"},
}

# Forbidden tag pairs for internal-only goals
_INTERNAL_BLOCK_ACTIONS = frozenset({"github_pr"})


def validate_synthesized_unit(unit_type: str, goal_description: str) -> bool:
    """v2.2.0 R6 hard-filter — block over-eager external ActionUnits.

    Returns False when unit_type is unsafe for the goal (e.g. GitHub PR on
    pure internal AWS audit without explicit github/pr intent).
    """
    goal_lower = (goal_description or "").lower()
    ut = (unit_type or "").lower()

    # Map ActionUnit class names to library keys
    if "github" in ut or ut.endswith("githubpr") or ut == "github_pr":
        key = "github_pr"
    elif "slack" in ut or ut == "slack_alert":
        key = "slack_alert"
    else:
        return True

    # Internal + GitHub blocked unless explicit external/code intent
    if "internal" in goal_lower and key in _INTERNAL_BLOCK_ACTIONS:
        needed = _ACTION_UNIT_REQUIREMENTS.get(key, set())
        if not (needed & set(re.findall(r"[a-z0-9]+", goal_lower))):
            return False

    # Require keyword intersection for action units
    needed = _ACTION_UNIT_REQUIREMENTS.get(key, set())
    kws = set(re.findall(r"[a-z0-9]+", goal_lower))
    if needed and not (needed & kws):
        return False
    return True


def _maybe_port_rank_units(
    goal: str,
    keys: List[str],
    synth: "CharterSynthesizer",
) -> Tuple[List[str], str]:
    """Optional Port rank. Heuristic wins unless a live Port confirms.

    Returns (keys, source) where source is one of:
      muscle_heuristic | port_ranked | port_rejected_keep_heuristic
    Never invents unit keys. R6 action filters still apply.
    """
    if not keys:
        return ["inventory", "validate"], "muscle_heuristic"
    client = getattr(synth, "llm_client", None)
    live = bool(getattr(getattr(client, "bridge", None), "live", False))
    if not live or client is None:
        return list(keys), "muscle_heuristic"
    try:
        from .production import LLMExecutionRequest

        allowed = ",".join(keys)
        resp = client.execute(
            LLMExecutionRequest(
                workload=(
                    f"Rank Flow Units for goal={goal!r}. "
                    f"Only choose from: {allowed}. "
                    "Put the ordered keys in output_payload.unit_keys."
                ),
                path="path_lite",
                termination_risk_index=0.12,
                system_prompt="Schema-strict charter synthesizer ranker.",
                playbook_constraints=[
                    "Do not invent unit keys",
                    "R6: no GitHub unless goal has github/pr intent",
                    "JSON envelope only",
                ],
                expected_output_keys=["result", "quality", "path", "tokens"],
                agent_name="Synthesizer",
                role="Charter_Ranker",
            )
        )
        payload: Dict[str, Any] = {}
        if resp.output is not None:
            payload = dict(resp.output.output_payload or {})
        ranked = payload.get("unit_keys") or payload.get("keys") or []
        if not resp.ok or not isinstance(ranked, list) or not ranked:
            return list(keys), "port_rejected_keep_heuristic"
        cleaned: List[str] = []
        seen: set[str] = set()
        for raw in ranked:
            k = str(raw)
            if k not in _UNIT_LIBRARY or k in seen:
                continue
            if k in _ACTION_UNIT_REQUIREMENTS and not validate_synthesized_unit(
                k, goal
            ):
                continue
            seen.add(k)
            cleaned.append(k)
        if not cleaned:
            return list(keys), "port_rejected_keep_heuristic"
        return cleaned, "port_ranked"
    except Exception:  # noqa: BLE001 — Port is optional; heuristic is law
        return list(keys), "port_rejected_keep_heuristic"


def _select_unit_keys(goal: str, muscle_paths: Sequence[str]) -> List[str]:
    """Heuristic + muscle path → ordered unit library keys (R6 hard filters)."""
    kws = _goal_keywords(goal)
    selected: List[str] = ["inventory"]

    path_blob = " ".join(muscle_paths).lower()
    if kws & {"scan", "audit", "aws", "security", "cve", "vuln"} or "swarm" in path_blob:
        selected.append("swarm_scan")
    if kws & {"migrate", "migration", "stripe", "paypal", "billing", "etl", "transform"}:
        selected.append("transform")
    if "validate" not in selected:
        selected.append("validate")

    # R6: GitHub only on explicit intent — NOT via soft muscle path alone
    if kws & {"github", "pr", "patch", "diff", "repo", "commit", "pull"}:
        if validate_synthesized_unit("github_pr", goal):
            selected.append("github_pr")
    # R6: Slack only on explicit notify intent
    if kws & {"slack", "alert", "notify", "webhook", "channel"}:
        if validate_synthesized_unit("slack_alert", goal):
            selected.append("slack_alert")

    # Deduplicate preserve order
    seen = set()
    out: List[str] = []
    for k in selected:
        if k not in seen and k in _UNIT_LIBRARY:
            # Final gate for action library keys
            if k in _ACTION_UNIT_REQUIREMENTS:
                if not validate_synthesized_unit(k, goal):
                    continue
            seen.add(k)
            out.append(k)
    return out or ["inventory", "validate"]


def _unit_from_lib(key: str, order: int) -> FlowUnitDraft:
    lib = _UNIT_LIBRARY[key]
    uid = lib["id"] if order == 0 else lib["id"]
    # renumber for uniqueness
    uid = f"U{order + 1}_{uid.split('_', 1)[-1]}" if "_" in uid else f"U{order + 1}_{uid}"
    return FlowUnitDraft(
        id=uid,
        description=str(lib["description"]),
        assigned_role=str(lib["role"]),
        expected_tokens=int(lib["tokens"]),
        expected_latency_ms=float(lib.get("latency", 400.0)),
        unit_kind=str(lib.get("kind", "flow")),
        action=lib.get("action"),
        swarm=bool(lib.get("swarm", False)),
        swarm_max_workers=int(lib.get("swarm_max_workers", 8)),
        schema_fields=dict(lib.get("schema") or {}),
        action_config=dict(lib.get("action_config") or {}),
    )


def _roster_from_units(units: Sequence[FlowUnitDraft]) -> List[RosterDraft]:
    by_role: Dict[str, set] = {}
    for u in units:
        key = u.assigned_role
        # pull caps from library by matching role
        caps: List[str] = []
        for lib in _UNIT_LIBRARY.values():
            if lib["role"] == u.assigned_role:
                caps = list(lib.get("caps") or [])
                break
        if not caps:
            caps = ["general"]
        by_role.setdefault(key, set()).update(caps)
    return [
        RosterDraft(role=role, capabilities=sorted(caps))
        for role, caps in by_role.items()
    ]


def charter_to_yaml(charter: SynthesizedCharterSchema) -> str:
    """Render SynthesizedCharterSchema → Charterfile YAML string."""
    doc: Dict[str, Any] = {
        "playbook_name": charter.playbook_name,
        "version": charter.version,
        "global_cfo_ceiling": int(charter.global_cfo_ceiling),
        "roster_requisition": [
            {"role": r.role, "capabilities": list(r.capabilities)}
            for r in charter.roster_requisition
        ],
        "flow_units": [],
    }
    for u in charter.flow_units:
        unit: Dict[str, Any] = {
            "id": u.id,
            "description": u.description,
            "assigned_role": u.assigned_role,
            "expected_tokens": u.expected_tokens,
            "expected_latency_ms": u.expected_latency_ms,
            "schema": dict(u.schema_fields) or {"result": "string", "quality": "float"},
        }
        if u.unit_kind == "swarm" or u.swarm:
            unit["unit_kind"] = "swarm"
            unit["swarm"] = True
            unit["swarm_max_workers"] = u.swarm_max_workers
        if u.unit_kind == "action" and u.action:
            unit["unit_kind"] = "action"
            unit["action"] = u.action
            if u.action_config:
                unit["action_config"] = dict(u.action_config)
        doc["flow_units"].append(unit)

    header = (
        "# FlowChartCharter — Synthesized Charterfile (v2.1 Coach Trust)\n"
        f"# muscle_memory_ids: {', '.join(charter.muscle_memory_ids) or 'none'}\n"
        f"# rationale: {charter.rationale[:200].replace(chr(10), ' ')}\n"
    )
    body = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)
    return header + body


def audit_cfo_ceiling(
    charter: SynthesizedCharterSchema,
    *,
    coach_ceiling: int,
    hard_cap: Optional[int] = None,
) -> Tuple[SynthesizedCharterSchema, CfoCeilingAudit]:
    """Ensure global_cfo_ceiling and unit sums respect coach budget.

    Returns (possibly adjusted charter, audit report).
    """
    findings: List[str] = []
    coach = max(100, int(coach_ceiling))
    hard = int(hard_cap) if hard_cap is not None else coach
    sum_tokens = sum(max(0, u.expected_tokens) for u in charter.flow_units)
    proposed = int(charter.global_cfo_ceiling)

    adjusted = proposed
    if proposed > coach:
        findings.append(
            f"proposed_ceiling {proposed} > coach_ceiling {coach}; clamped"
        )
        adjusted = coach
    if sum_tokens > adjusted:
        # Lift ceiling to cover sum if still under coach, else shrink unit budgets
        if sum_tokens <= coach:
            findings.append(
                f"sum_expected_tokens {sum_tokens} > ceiling {adjusted}; "
                f"lift ceiling to {sum_tokens}"
            )
            adjusted = sum_tokens
        else:
            findings.append(
                f"sum_expected_tokens {sum_tokens} exceeds coach {coach}; "
                "scale unit expected_tokens"
            )
            scale = coach / max(1, sum_tokens)
            new_units: List[FlowUnitDraft] = []
            for u in charter.flow_units:
                nt = max(50, int(u.expected_tokens * scale))
                new_units.append(u.model_copy(update={"expected_tokens": nt}))
            charter = charter.model_copy(update={"flow_units": new_units})
            sum_tokens = sum(u.expected_tokens for u in charter.flow_units)
            adjusted = min(coach, max(sum_tokens, 100))

    if adjusted > hard:
        findings.append(f"hard_cap {hard} applied")
        adjusted = hard

    # 15% contingency if room
    contingency = int(sum_tokens * 1.15) if sum_tokens else adjusted
    if contingency <= coach and contingency > adjusted:
        findings.append("applied 15% contingency buffer under coach ceiling")
        adjusted = contingency

    charter = charter.model_copy(
        update={
            "global_cfo_ceiling": int(adjusted),
            "estimated_token_total": int(sum_tokens),
        }
    )
    passed = (
        charter.global_cfo_ceiling <= coach
        and charter.estimated_token_total <= charter.global_cfo_ceiling
        and charter.global_cfo_ceiling > 0
    )
    if not passed:
        findings.append("CFO audit FAILED after adjustments")
    else:
        findings.append("CFO audit PASSED")

    audit = CfoCeilingAudit(
        passed=passed,
        coach_ceiling=coach,
        proposed_ceiling=proposed,
        sum_expected_tokens=int(sum_tokens),
        adjusted_ceiling=int(charter.global_cfo_ceiling),
        findings=findings,
    )
    return charter, audit


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass
class CharterSynthesizer:
    """Boss-facing synthesizer: goal → pending YAML draft."""

    muscle_db: Optional[MuscleMemoryVectorDB] = None
    coach_ceiling: int = 12_000
    drafts: Dict[str, CharterDraft] = field(default_factory=dict)
    llm_client: Any = None
    synthesizes: int = 0
    approvals: int = 0
    rejections: int = 0

    def synthesize(
        self,
        goal: str,
        *,
        coach_ceiling: Optional[int] = None,
        playbook_name: Optional[str] = None,
        force_units: Optional[Sequence[str]] = None,
    ) -> CharterDraft:
        """Query muscle memory + build schema-valid YAML draft (pending)."""
        goal = (goal or "").strip()
        if not goal:
            raise ValueError("goal must be non-empty")

        ceiling = int(coach_ceiling or self.coach_ceiling)
        muscle_hits = self._query_muscle(goal)
        paths: List[str] = []
        mem_ids: List[str] = []
        for hit in muscle_hits:
            paths.extend(hit.get("successful_flow_path") or [])
            if hit.get("memory_id"):
                mem_ids.append(str(hit["memory_id"]))

        keys = list(force_units) if force_units else _select_unit_keys(goal, paths)
        source = "muscle_heuristic"
        keys, source = _maybe_port_rank_units(goal, keys, self)
        units = [_unit_from_lib(k, i) for i, k in enumerate(keys)]
        roster = _roster_from_units(units)

        name = playbook_name or self._name_from_goal(goal)
        rationale = self._rationale(goal, muscle_hits, keys)

        draft_schema = SynthesizedCharterSchema(
            playbook_name=name,
            version="2.1.0",
            global_cfo_ceiling=ceiling,
            roster_requisition=roster,
            flow_units=units,
            rationale=rationale,
            muscle_memory_ids=mem_ids,
            estimated_token_total=sum(u.expected_tokens for u in units),
        )
        draft_schema, cfo_audit = audit_cfo_ceiling(
            draft_schema, coach_ceiling=ceiling
        )
        if not cfo_audit.passed:
            raise PlaybookCompileError(
                f"CFO ceiling audit failed: {cfo_audit.findings}"
            )

        yaml_text = charter_to_yaml(draft_schema)

        # Compile dry-run to guarantee Charterfile validity before Coach sees it
        try:
            compiled = compile_playbook(yaml_text)
        except PlaybookCompileError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise PlaybookCompileError(f"synthesize compile failed: {exc}") from exc

        # Rhythm marker — synthesis quality
        quality = 0.96 if muscle_hits else 0.91
        rhythm = RhythmAudit(
            marker="coach_trust_synthesize",
            charter_id=compiled.playbook_id
            if hasattr(compiled, "playbook_id")
            else draft_schema.playbook_name,
            quality=quality,
            threshold=0.90,
            passed=quality >= 0.90 and cfo_audit.passed,
            remediation_loops=0,
            blocking_issues=tuple(
                [] if cfo_audit.passed else ["cfo_audit_failed"]
            ),
        ).to_dict()

        draft_id = f"DRAFT-{uuid.uuid4().hex[:10].upper()}"
        draft = CharterDraft(
            draft_id=draft_id,
            status=CharterDraftStatus.PENDING_COACH_APPROVAL,
            goal=goal,
            yaml_text=yaml_text,
            charter=draft_schema,
            cfo_audit=cfo_audit,
            muscle_hits=muscle_hits,
            rhythm_audit=rhythm,
            synthesis_source=source,
        )
        self.drafts[draft_id] = draft
        self.synthesizes += 1
        return draft

    def get_draft(self, draft_id: str) -> Optional[CharterDraft]:
        return self.drafts.get(draft_id)

    def list_pending(self) -> List[CharterDraft]:
        return [
            d
            for d in self.drafts.values()
            if d.status == CharterDraftStatus.PENDING_COACH_APPROVAL
        ]

    def approve(
        self,
        draft_id: str,
        *,
        approved_by: str = "Head Coach",
        auto_load: bool = True,
        system: Any = None,
    ) -> Dict[str, Any]:
        """1-click Coach approval — promote draft to executable playbook."""
        draft = self.drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"unknown draft_id {draft_id}")
        if draft.status != CharterDraftStatus.PENDING_COACH_APPROVAL:
            raise ValueError(
                f"draft {draft_id} is {draft.status.value}, not PENDING_COACH_APPROVAL"
            )
        # Re-audit CFO at approval time (coach ceiling may have changed)
        ceiling = int(
            getattr(system, "token_budget", None) or self.coach_ceiling
        )
        _, audit = audit_cfo_ceiling(draft.charter, coach_ceiling=ceiling)
        if not audit.passed:
            raise PlaybookCompileError(
                f"approval blocked by CFO audit: {audit.findings}"
            )

        draft.status = CharterDraftStatus.APPROVED
        draft.approved_at = time.time()
        draft.approved_by = approved_by
        draft.cfo_audit = audit
        self.approvals += 1

        load_meta: Optional[Dict[str, Any]] = None
        if auto_load and system is not None and hasattr(system, "load_playbook"):
            load_meta = system.load_playbook(
                draft.yaml_text, source_path=f"synth:{draft.draft_id}"
            )
            # Bind pending clearance on boss
            if hasattr(system, "boss") and hasattr(
                system.boss, "clear_pending_charter"
            ):
                system.boss.clear_pending_charter(draft.draft_id)

        return {
            "draft_id": draft.draft_id,
            "status": draft.status.value,
            "approved_by": approved_by,
            "approved_at": draft.approved_at,
            "cfo_audit": audit.model_dump(),
            "load": load_meta,
            "yaml_text": draft.yaml_text,
            "playbook_name": draft.charter.playbook_name,
        }

    def reject(
        self,
        draft_id: str,
        *,
        reason: str = "coach_rejected",
        system: Any = None,
    ) -> Dict[str, Any]:
        draft = self.drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"unknown draft_id {draft_id}")
        if draft.status != CharterDraftStatus.PENDING_COACH_APPROVAL:
            raise ValueError(f"draft not pending: {draft.status.value}")
        draft.status = CharterDraftStatus.REJECTED
        draft.rejected_at = time.time()
        self.rejections += 1
        if system is not None and hasattr(system, "boss"):
            if hasattr(system.boss, "clear_pending_charter"):
                system.boss.clear_pending_charter(draft.draft_id)
        return {
            "draft_id": draft_id,
            "status": draft.status.value,
            "reason": reason,
            "rejected_at": draft.rejected_at,
        }

    def mark_executed(
        self, draft_id: str, result: Mapping[str, Any]
    ) -> None:
        draft = self.drafts.get(draft_id)
        if draft is None:
            return
        draft.status = CharterDraftStatus.EXECUTED
        draft.execution_result = dict(result)

    def _query_muscle(self, goal: str) -> List[Dict[str, Any]]:
        if self.muscle_db is None:
            return []
        payload = {"goal": goal, "job_type": goal[:80]}
        hits = self.muscle_db.query_top_k(payload, threshold=0.55, top_k=5)
        if hits:
            return hits
        # Seed synthetic memory from goal keywords for cold start density
        return self._cold_start_hints(goal)

    def _cold_start_hints(self, goal: str) -> List[Dict[str, Any]]:
        kws = _goal_keywords(goal)
        path = ["U1_Inventory"]
        if kws & {"scan", "audit", "aws"}:
            path.append("U2_Swarm_Scan")
        if kws & {"migrate", "billing"}:
            path.append("U3_Transform")
        path.append("U4_Validate")
        if kws & {"slack", "alert"}:
            path.append("U6_Slack_Alert")
        if kws & {"github", "pr", "patch"}:
            path.append("U5_Open_GitHub_PR")
        rec = ExecutionMemoryRecord(
            memory_id=f"MEM-COLD-{uuid.uuid4().hex[:6].upper()}",
            job_type=goal[:80],
            state_vector=encode_state({"goal": goal}),
            successful_flow_path=path,
            entanglement_score=0.9,
            prompt_tweak="prefer schema-locked units; dry-run actions",
            quality=0.93,
            token_cost=sum(
                _UNIT_LIBRARY.get(k, {}).get("tokens", 500)
                for k in ("inventory", "validate")
            ),
            tags=tuple(sorted(kws)[:8]),
        )
        if self.muscle_db is not None:
            self.muscle_db.commit_memory(rec)
        return [
            {
                "memory_id": rec.memory_id,
                "job_type": rec.job_type,
                "similarity": 0.8,
                "successful_flow_path": list(rec.successful_flow_path),
                "entanglement_score": rec.entanglement_score,
                "prompt_tweak": rec.prompt_tweak,
                "quality": rec.quality,
                "token_cost": rec.token_cost,
                "tags": list(rec.tags),
                "cold_start": True,
            }
        ]

    @staticmethod
    def _name_from_goal(goal: str) -> str:
        slug = re.sub(r"\s+", " ", goal.strip())
        if len(slug) > 60:
            slug = slug[:57] + "..."
        return f"Synth: {slug}"

    @staticmethod
    def _rationale(
        goal: str,
        hits: Sequence[Mapping[str, Any]],
        keys: Sequence[str],
    ) -> str:
        if hits:
            top = hits[0]
            return (
                f"Muscle-Memory trajectory {top.get('memory_id')} "
                f"(sim={top.get('similarity')}) informed units {list(keys)} "
                f"for goal: {goal[:120]}"
            )
        return f"Heuristic unit pack {list(keys)} for novel goal: {goal[:120]}"

    def stats(self) -> Dict[str, Any]:
        pending = sum(
            1
            for d in self.drafts.values()
            if d.status == CharterDraftStatus.PENDING_COACH_APPROVAL
        )
        return {
            "version": "2.1.0",
            "synthesizes": self.synthesizes,
            "approvals": self.approvals,
            "rejections": self.rejections,
            "drafts_total": len(self.drafts),
            "pending": pending,
            "coach_ceiling": self.coach_ceiling,
        }


def seed_synthesis_memories(db: MuscleMemoryVectorDB) -> int:
    """Seed proven multi-unit trajectories for common enterprise goals."""
    seeds = [
        (
            "aws infrastructure audit slack alert",
            ["U1_Inventory", "U2_Swarm_Scan", "U4_Validate", "U6_Slack_Alert"],
            ("aws", "audit", "slack"),
        ),
        (
            "billing migration stripe paypal",
            ["U1_Inventory", "U3_Transform", "U4_Validate", "U5_Open_GitHub_PR"],
            ("billing", "migrate", "stripe", "paypal"),
        ),
        (
            "secops vulnerability patch github pr",
            [
                "U1_Inventory",
                "U2_Swarm_Scan",
                "U3_Transform",
                "U5_Open_GitHub_PR",
                "U6_Slack_Alert",
            ],
            ("secops", "patch", "github"),
        ),
    ]
    n = 0
    for job, path, tags in seeds:
        rec = ExecutionMemoryRecord(
            memory_id=f"MEM-SEED-{uuid.uuid4().hex[:6].upper()}",
            job_type=job,
            state_vector=encode_state({"goal": job, "job_type": job}),
            successful_flow_path=list(path),
            entanglement_score=0.92,
            prompt_tweak="reuse validated unit pack; keep actions dry-run",
            quality=0.96,
            token_cost=3500,
            tags=tags,
        )
        db.commit_memory(rec)
        n += 1
    return n
