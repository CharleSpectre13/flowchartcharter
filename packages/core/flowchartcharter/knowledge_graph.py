"""FlowChartCharter Brain 1 — hierarchical knowledge graph (graph-engineering).

GraphRAG remains a *callable sub-flow* for pure relational discovery.
The Charter owns execution; this graph owns durable domain ontology + memory.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set
import json
import re


@dataclass
class Entity:
    id: str
    title: str
    type: str  # Concept | Structure | Role | Mechanism | Metric | Goal | Phase
    description: str
    community: str
    importance: float = 0.5
    sources: List[str] = field(default_factory=list)


@dataclass
class Relation:
    src: str
    dst: str
    type: str  # owns | implements | measures | reports_to | enables | collapses_to | uses
    description: str
    strength: float = 1.0


# ── Communities (Leiden-style partitions from mind map) ──────────────────────
COMMUNITIES = {
    "core_concept": "Core Concept — execution-first paradigm",
    "foundational": "Foundational Structures — DNA of FCC",
    "hierarchy": "Corporate Hierarchy — accountability ladder",
    "operations": "Operational Mechanisms — rhythm & trust",
    "math": "Mathematical Framework — quantum routing & fitness",
    "goals": "Strategic Goals — earned trust at scale",
    "phases": "Lifecycle Phases ST-01…ST-07",
}


def build_ontology() -> Dict[str, Any]:
    """Authoritative ontology distilled from Drive blueprints + mind map + spreadsheet."""
    entities: List[Entity] = [
        # Core concept
        Entity(
            "fcc",
            "FlowChartCharter Engineering",
            "Concept",
            "Execution-and-quality-first multi-agent state-chart systems; agents follow rather than search.",
            "core_concept",
            1.0,
            ["Drive:Blueprint", "Drive:ArchSpec", "IMG:mindmap"],
        ),
        Entity(
            "exec_over_retrieval",
            "Execution over Retrieval",
            "Concept",
            "Primary focus is fastest reliable path to completion, not open graph lookup.",
            "core_concept",
            0.95,
            ["Drive:Blueprint", "IMG:playbook"],
        ),
        Entity(
            "deterministic_playbooks",
            "Deterministic Playbooks",
            "Concept",
            "Pre-approved paths eliminate guesswork and execution drift.",
            "core_concept",
            0.9,
            ["Drive:HeadCoach"],
        ),
        Entity(
            "unified_multi_agent",
            "Unified Multi-Agent Architecture",
            "Concept",
            "Corporate hierarchy + BSP super-steps + Blackboard volunteer binding.",
            "core_concept",
            0.9,
            ["Drive:SystemDesign"],
        ),
        Entity(
            "self_optimizing",
            "Self-Optimizing System",
            "Concept",
            "Async RLAIF via Monday Morning Sync raises benchmarks without human micro-management.",
            "core_concept",
            0.9,
            ["Drive:Blueprint"],
        ),
        # Foundational structures
        Entity(
            "charter",
            "Charter (Pre-drawn Map)",
            "Structure",
            "Quantum measurement operator M that collapses path superposition into deterministic action.",
            "foundational",
            1.0,
            ["Spreadsheet:Table1", "Drive:ArchSpec"],
        ),
        Entity(
            "flow_units",
            "Flow Units (Type-safe Contracts)",
            "Structure",
            "Discrete modules |FlowUnit_i⟩ with explicit I/O and exit criteria.",
            "foundational",
            0.95,
            ["Spreadsheet:Table1"],
        ),
        Entity(
            "rhythm_markers",
            "Rhythm Markers (Validation Points)",
            "Structure",
            "Self-auditing checkpoints that force wave-function collapse before Blackboard commit.",
            "foundational",
            0.95,
            ["Spreadsheet:Table1", "IMG:playbook"],
        ),
        Entity(
            "muscle_memory",
            "Muscle-Memory Loop",
            "Structure",
            "Historical success amplitudes c_i weight future path selection; autonomous correction.",
            "foundational",
            0.95,
            ["Spreadsheet:Table1"],
        ),
        Entity(
            "engineer_exit",
            "Engineer Exit / Coach Trust Hand-Off",
            "Structure",
            "Milestone of Earned Engineering Trust — Head Coach steps back without stepping out.",
            "foundational",
            1.0,
            ["Spreadsheet:Table1", "Drive:HeadCoach"],
        ),
        Entity(
            "monday_sync",
            "Monday Morning Sync (Async RLAIF)",
            "Structure",
            "ST-07 downtime talent + prompt optimization under Boss Agent leadership.",
            "foundational",
            0.9,
            ["Spreadsheet:Table1", "IMG:playbook"],
        ),
        # Hierarchy
        Entity(
            "ceo",
            "CEO Agent",
            "Role",
            "Strategic vectors; intervenes only on sync/forks.",
            "hierarchy",
            0.85,
            ["Drive:Blueprint"],
        ),
        Entity(
            "cfo",
            "CFO Agent",
            "Role",
            "BudgetVector; token spend vs cap; halt_if_over.",
            "hierarchy",
            0.85,
            ["Drive:Blueprint"],
        ),
        Entity(
            "board",
            "Executive Board",
            "Role",
            "GovernanceVector; approves Coach Trust Hand-Off.",
            "hierarchy",
            0.9,
            ["Drive:ArchSpec"],
        ),
        Entity(
            "gm",
            "General Manager (Boss Agent)",
            "Role",
            "Day-to-day ops buffer; OpsVector talent outcomes.",
            "hierarchy",
            1.0,
            ["IMG:playbook"],
        ),
        Entity(
            "position_mgr",
            "Position Managers",
            "Role",
            "Segment oversight of charter sub-flows.",
            "hierarchy",
            0.7,
            ["Drive:HeadCoach"],
        ),
        Entity(
            "key_players",
            "Key Players",
            "Role",
            "Execute flow units under typed contracts.",
            "hierarchy",
            0.8,
            ["Drive:HeadCoach"],
        ),
        Entity(
            "coaches",
            "Coaches and Architects",
            "Role",
            "Structural integrity and rhythm optimization.",
            "hierarchy",
            0.75,
            ["Drive:HeadCoach"],
        ),
        Entity(
            "head_coach",
            "Human Head Coach",
            "Role",
            "System Architect; designs Charter, earns trust exit.",
            "hierarchy",
            1.0,
            ["Drive:HeadCoach"],
        ),
        Entity(
            "validator",
            "Rhythm Marker Validator",
            "Role",
            "Maker-checker at gates; never the implementor.",
            "hierarchy",
            0.9,
            ["skill:rhythm-marker-validator"],
        ),
        # Mechanisms
        Entity(
            "blackboard",
            "Blackboard (Structured Communication)",
            "Mechanism",
            "JSON performance vectors only — forbids free-form NL among agents.",
            "operations",
            0.95,
            ["Drive:Blueprint"],
        ),
        Entity(
            "talent_mgmt",
            "Dynamic Talent Management",
            "Mechanism",
            "Promote / demote / fire by fitness during Monday Morning Sync.",
            "operations",
            0.9,
            ["Drive:Blueprint"],
        ),
        Entity(
            "bsp",
            "BSP Super-Step Engine",
            "Mechanism",
            "Pregel-style parallel execution with deterministic channel reducers.",
            "operations",
            0.85,
            ["Drive:SystemDesign"],
        ),
        # Math
        Entity(
            "superposition",
            "Quantum Path Superposition",
            "Metric",
            "|ψ⟩ = Σ c_i |FlowUnit_i⟩ with c_i from muscle-memory success rates.",
            "math",
            0.95,
            ["Drive:ArchSpec", "IMG:playbook"],
        ),
        Entity(
            "collapse",
            "Wave Function Collapse (Measurement)",
            "Metric",
            "|ExecutedPath⟩ = M|ψ⟩ at Rhythm Markers — 100% confident action.",
            "math",
            0.95,
            ["Drive:ArchSpec"],
        ),
        Entity(
            "fitness_score",
            "Agent Fitness Score F(x)",
            "Metric",
            "F = α·(Q_success/Q_total) + β·(1/Δt) − γ·Tokens + Q_entanglement",
            "math",
            1.0,
            ["Drive:Blueprint"],
        ),
        Entity(
            "synergy",
            "Synergy Entanglement Score",
            "Metric",
            "How seamlessly agent output integrates into next unit without friction.",
            "math",
            0.9,
            ["Drive:Blueprint"],
        ),
        # Goals
        Entity(
            "earned_trust",
            "Earned Engineering Trust",
            "Goal",
            "Empirically proven reliability enabling human-out-of-loop scale.",
            "goals",
            1.0,
            ["Drive:HeadCoach"],
        ),
        Entity(
            "no_micromanage",
            "Eliminate Micro-management",
            "Goal",
            "Engineer designs playbook and steps back as Head Coach.",
            "goals",
            0.9,
            ["Drive:HeadCoach"],
        ),
        Entity(
            "latency_cost",
            "Latency and Cost Reduction",
            "Goal",
            "First-class metrics; type-safe contracts kill token bloat.",
            "goals",
            0.9,
            ["Drive:ArchSpec"],
        ),
        Entity(
            "scalable_perf",
            "Scalable Performance",
            "Goal",
            "Measured by agents-on-charter and human-out-of-loop time.",
            "goals",
            0.95,
            ["Drive:ArchSpec"],
        ),
        # Phases
        Entity(
            "st01",
            "ST-01 Charter Init",
            "Phase",
            "Board + Boss intake; StrategyVector.",
            "phases",
            0.7,
        ),
        Entity(
            "st02",
            "ST-02 Voluntary Bind",
            "Phase",
            "Blackboard volunteer capability×rank match.",
            "phases",
            0.7,
        ),
        Entity(
            "st03", "ST-03 Super-Step", "Phase", "BSP parallel flow unit execution.", "phases", 0.7
        ),
        Entity(
            "st04", "ST-04 Rhythm Audit", "Phase", "Independent RhythmAudit gate.", "phases", 0.85
        ),
        Entity(
            "st05",
            "ST-05 Muscle Memory",
            "Phase",
            "Remediation from checkpoints (max 3).",
            "phases",
            0.7,
        ),
        Entity(
            "st06",
            "ST-06 Coach Trust",
            "Phase",
            "GovernanceVector approve_hand_off.",
            "phases",
            0.9,
        ),
        Entity(
            "st07",
            "ST-07 Monday Sync",
            "Phase",
            "Talent + RLAIF downtime optimization.",
            "phases",
            0.85,
        ),
    ]

    relations: List[Relation] = [
        Relation("fcc", "exec_over_retrieval", "owns", "paradigm pillar"),
        Relation("fcc", "deterministic_playbooks", "owns", "paradigm pillar"),
        Relation("fcc", "unified_multi_agent", "owns", "paradigm pillar"),
        Relation("fcc", "self_optimizing", "owns", "paradigm pillar"),
        Relation("fcc", "charter", "implements", "DNA structure"),
        Relation("charter", "flow_units", "owns", "building blocks"),
        Relation("charter", "rhythm_markers", "owns", "validation points"),
        Relation("charter", "muscle_memory", "uses", "path amplitudes"),
        Relation("rhythm_markers", "collapse", "enables", "measurement M"),
        Relation("superposition", "collapse", "collapses_to", "deterministic path"),
        Relation("muscle_memory", "superposition", "enables", "sets c_i amplitudes"),
        Relation("charter", "superposition", "implements", "operator M"),
        Relation("board", "gm", "owns", "oversight"),
        Relation("ceo", "board", "reports_to", "exec layer"),
        Relation("cfo", "board", "reports_to", "exec layer"),
        Relation("gm", "position_mgr", "owns", "ops buffer"),
        Relation("position_mgr", "key_players", "owns", "execution"),
        Relation("head_coach", "engineer_exit", "enables", "trust milestone"),
        Relation("validator", "rhythm_markers", "implements", "maker-checker"),
        Relation("gm", "monday_sync", "implements", "ST-07 leadership"),
        Relation("monday_sync", "talent_mgmt", "enables", "promote/fire"),
        Relation("fitness_score", "talent_mgmt", "measures", "promotability"),
        Relation("synergy", "fitness_score", "enables", "entanglement term"),
        Relation("blackboard", "ceo", "uses", "StrategyVector"),
        Relation("blackboard", "cfo", "uses", "BudgetVector"),
        Relation("blackboard", "board", "uses", "GovernanceVector"),
        Relation("blackboard", "gm", "uses", "OpsVector"),
        Relation("engineer_exit", "earned_trust", "enables", "strategic goal"),
        Relation("st04", "rhythm_markers", "implements", "gate phase"),
        Relation("st06", "engineer_exit", "implements", "hand-off phase"),
        Relation("st07", "monday_sync", "implements", "sync phase"),
        Relation("flow_units", "key_players", "uses", "execution tier"),
        Relation("bsp", "st03", "implements", "super-step"),
        Relation("latency_cost", "cfo", "measures", "token governance"),
        Relation("scalable_perf", "earned_trust", "enables", "human-out-of-loop"),
    ]

    return {
        "version": "0.3.0",
        "paradigm": "Charter primary; GraphRAG callable sub-flow only",
        "communities": COMMUNITIES,
        "entities": [asdict(e) for e in entities],
        "relations": [asdict(r) for r in relations],
        "community_reports": _community_reports(entities, relations),
        "text_units": [],
        "full_rebuild": False,
        "sources": {
            "drive": [
                "The FlowChartCharter Blueprint (Corporate Governance)",
                "FlowChartCharter: Head Coach Guide",
                "Architectural Specification",
                "Engineering System Design",
                "System Design and Structure (spreadsheet)",
            ],
            "images": ["IMG_0544 mind map", "IMG_0542 hierarchy+playbook"],
        },
    }


def _community_reports(
    entities: List[Entity], relations: List[Relation]
) -> Dict[str, Dict[str, Any]]:
    by: Dict[str, List[Entity]] = {}
    for e in entities:
        by.setdefault(e.community, []).append(e)
    reports = {}
    for cid, members in by.items():
        titles = [m.title for m in sorted(members, key=lambda x: -x.importance)]
        reports[cid] = {
            "title": COMMUNITIES.get(cid, cid),
            "executive_summary": f"{COMMUNITIES.get(cid, cid)}: {', '.join(titles[:5])}",
            "entity_count": len(members),
            "top_entities": titles[:8],
            "importance": max(m.importance for m in members),
        }
    return reports


class KnowledgeGraph:
    """In-memory hierarchical KG for local / global style queries over FCC ontology."""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self.data = data or build_ontology()
        self.data.setdefault("text_units", [])
        self.data.setdefault("full_rebuild", False)
        self.data.setdefault("aliases", {})
        self._reindex()

    def _reindex(self) -> None:
        """Rebuild adjacency only. Not a corpus rebuild."""
        self._by_id = {
            e["id"]: e for e in self.data.get("entities") or [] if isinstance(e, dict)
        }
        self._out = {}
        self._in = {}
        for r in self.data.get("relations") or []:
            if not isinstance(r, dict):
                continue
            self._out.setdefault(r["src"], []).append(r)
            self._in.setdefault(r["dst"], []).append(r)

    def resolve_alias(self, name: str) -> str:
        from .charter_memory import stable_id

        raw = (name or "").strip()
        slug = stable_id(raw)
        aliases = self.data.setdefault("aliases", {})
        if raw.lower() in aliases:
            return str(aliases[raw.lower()])
        if slug in aliases:
            return str(aliases[slug])
        if slug in self._by_id:
            return slug
        return slug

    def register_alias(self, title: str, eid: str) -> None:
        from .charter_memory import stable_id

        aliases = self.data.setdefault("aliases", {})
        if title:
            aliases[title.lower()] = eid
        aliases[stable_id(title)] = eid
        aliases[eid] = eid

    def entity_count(self) -> int:
        return len(self.data.get("entities") or [])

    def ingest_delta(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        *,
        text_unit: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Delta upsert. {not full_rebuild} ingest {not full_rebuild ∧ |E|'>=|E|}."""
        from .charter_memory import MergeReceipt

        before = self.entity_count()
        by_id = {
            e["id"]: e for e in self.data["entities"] if isinstance(e, dict)
        }
        added = 0
        updated = 0
        for raw in entities:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            eid = str(raw["id"])
            title = str(raw.get("title") or "")
            if title:
                aliased = self.resolve_alias(title)
                if aliased in by_id:
                    eid = aliased
                    raw["id"] = eid
            if eid in by_id:
                updated += 1
                old = by_id[eid]
                srcs = list(
                    dict.fromkeys(
                        list(old.get("sources") or []) + list(raw.get("sources") or [])
                    )
                )
                old["sources"] = srcs
                desc = str(raw.get("description") or "")
                if desc and len(desc) > len(str(old.get("description") or "")):
                    old["description"] = desc
            else:
                row = dict(raw)
                row.setdefault("community", "fcc_community")
                row.setdefault("type", "Concept")
                row.setdefault("importance", 0.55)
                self.data["entities"].append(row)
                by_id[eid] = row
                added += 1
                self.register_alias(str(row.get("title") or eid), eid)
        rel_keys = {
            (r.get("src"), r.get("dst"), r.get("type"))
            for r in self.data["relations"]
            if isinstance(r, dict)
        }
        rel_added = 0
        for raw in relations:
            if not isinstance(raw, dict):
                continue
            key = (raw.get("src"), raw.get("dst"), raw.get("type"))
            if key in rel_keys or not key[0] or not key[1]:
                continue
            self.data["relations"].append(dict(raw))
            rel_keys.add(key)
            rel_added += 1
        if text_unit:
            row = dict(text_unit)
            row.setdefault("valid", True)
            sid = str(row.get("source_id") or "")
            uid = str(row.get("unit_id") or "")
            if sid:
                self.supersede_units(sid, keep_id=uid)
            self.data.setdefault("text_units", []).append(row)
        self.data["full_rebuild"] = False
        self._reindex()
        self._refresh_fcc_communities()
        return MergeReceipt(
            added=added,
            updated=updated,
            relations_added=rel_added,
            entity_count_before=before,
            entity_count_after=self.entity_count(),
            full_rebuild=False,
            source_id=str((text_unit or {}).get("source_id") or ""),
        )

    def append_text_unit(self, text_unit: Dict[str, Any]) -> None:
        """Store a note even when extract fails. House drip."""
        row = dict(text_unit)
        row.setdefault("valid", True)
        sid = str(row.get("source_id") or "")
        uid = str(row.get("unit_id") or "")
        if sid:
            self.supersede_units(sid, keep_id=uid)
        self.data.setdefault("text_units", []).append(row)

    def _refresh_fcc_communities(self) -> None:
        by: Dict[str, List[Dict[str, Any]]] = {}
        for ent in self.data.get("entities") or []:
            if not isinstance(ent, dict):
                continue
            cid = str(ent.get("community") or "fcc_community")
            by.setdefault(cid, []).append(ent)
        reports: Dict[str, Dict[str, Any]] = {}
        labels = dict(COMMUNITIES)
        labels.setdefault("fcc_community", "FCC incremental community")
        for cid, members in by.items():
            titles = [
                str(m.get("title") or m.get("id"))
                for m in sorted(
                    members, key=lambda x: -float(x.get("importance") or 0)
                )
            ]
            reports[cid] = {
                "id": cid,
                "title": labels.get(cid, cid),
                "executive_summary": f"{labels.get(cid, cid)}: {', '.join(titles[:5])}",
                "entity_count": len(members),
                "top_entities": titles[:8],
                "importance": max(
                    float(m.get("importance") or 0) for m in members
                ),
            }
        self.data["community_reports"] = reports

    def lazy_search(self, query: str, top_k: int = 8) -> Dict[str, Any]:
        """Query-time concept overlap. Backend name is fcc_lazy, not GraphRAG."""
        q = (query or "").lower()
        tokens = [t for t in re.findall(r"[a-z0-9_]{3,}", q)]
        scored: List[tuple[float, Dict[str, Any]]] = []
        for ent in self.data.get("entities") or []:
            if not isinstance(ent, dict):
                continue
            blob = " ".join(
                [
                    str(ent.get("id") or ""),
                    str(ent.get("title") or ""),
                    str(ent.get("description") or ""),
                ]
            ).lower()
            hits = sum(1 for t in tokens if t in blob)
            if not hits and q and q in blob:
                hits = 2
            if hits:
                scored.append((float(hits) + float(ent.get("importance") or 0), ent))
        scored.sort(key=lambda x: -x[0])
        nodes = [e for _, e in scored[: max(1, top_k)]]
        return {
            "query": query,
            "nodes": nodes,
            "backend": "fcc_lazy",
            "full_rebuild": False,
        }

    def supersede_units(self, source_id: str, *, keep_id: str = "") -> int:
        """Invalidate prior units that share a source/goal. Keep keep_id."""
        n = 0
        for unit in self.data.get("text_units") or []:
            if not isinstance(unit, dict):
                continue
            if str(unit.get("source_id") or "") != source_id:
                continue
            if keep_id and str(unit.get("unit_id") or "") == keep_id:
                continue
            if unit.get("valid", True):
                unit["valid"] = False
                n += 1
        return n

    def invalid_unit_ids(self) -> set[str]:
        ids: set[str] = set()
        for unit in self.data.get("text_units") or []:
            if not isinstance(unit, dict) or unit.get("valid", True):
                continue
            uid = str(unit.get("unit_id") or "")
            sid = str(unit.get("source_id") or "")
            if uid:
                ids.add(uid)
            if sid:
                ids.add(sid)
        return ids

    def search_units(self, query: str, top_k: int = 8) -> Dict[str, Any]:
        """Passage search over valid TextUnits. Not GraphRAG."""
        q = (query or "").lower()
        q_tokens = [t for t in re.findall(r"[a-z0-9_]{3,}", q)]
        scored: List[tuple[float, Dict[str, Any]]] = []
        units = [
            u
            for u in (self.data.get("text_units") or [])
            if isinstance(u, dict) and u.get("valid", True)
        ]
        df: Dict[str, int] = {}
        for unit in units:
            blob = str(unit.get("text") or "").lower()
            seen = set(re.findall(r"[a-z0-9_]{3,}", blob))
            for tok in seen:
                df[tok] = df.get(tok, 0) + 1
        n_docs = max(1, len(units))
        for unit in units:
            blob = str(unit.get("text") or "").lower()
            if not blob:
                continue
            tf_hits = 0.0
            for tok in q_tokens:
                tf = blob.count(tok)
                if tf:
                    idf = 1.0 + (n_docs / (1 + df.get(tok, 0)))
                    tf_hits += tf * idf
            if q and q in blob:
                tf_hits += 4.0
            if tf_hits <= 0:
                continue
            row = dict(unit)
            row["id"] = str(unit.get("unit_id") or "")
            row["title"] = str(unit.get("source_id") or row["id"])
            row["description"] = str(unit.get("text") or "")[:400]
            row["source"] = str(unit.get("unit_id") or unit.get("source_id") or "")
            row["score"] = tf_hits
            scored.append((tf_hits, row))
        scored.sort(key=lambda x: -x[0])
        return {
            "query": query,
            "units": [u for _, u in scored[: max(1, top_k)]],
            "backend": "fcc_units",
            "full_rebuild": False,
        }

    def local_search(self, entity_id: str, hops: int = 2) -> Dict[str, Any]:
        """1–2 hop expansion around an entity (local GraphRAG-style)."""
        if entity_id not in self._by_id:
            # fuzzy title match
            for e in self.data["entities"]:
                if entity_id.lower() in e["title"].lower() or entity_id.lower() in e["id"]:
                    entity_id = e["id"]
                    break
        visited: Set[str] = set()
        frontier = {entity_id}
        edges: List[Dict] = []
        for _ in range(hops):
            nxt: Set[str] = set()
            for n in frontier:
                if n in visited:
                    continue
                visited.add(n)
                for r in self._out.get(n, []) + self._in.get(n, []):
                    edges.append(r)
                    nxt.add(r["src"])
                    nxt.add(r["dst"])
            frontier = nxt - visited
        nodes = [self._by_id[i] for i in visited if i in self._by_id]
        return {"seed": entity_id, "nodes": nodes, "edges": edges}

    def global_search(self, theme: str = "") -> Dict[str, Any]:
        """Map-reduce over community reports (global sensemaking)."""
        reports = list(self.data["community_reports"].values())
        if theme:
            t = theme.lower()
            reports = [
                r for r in reports if t in r["title"].lower() or t in r["executive_summary"].lower()
            ]
            if not reports:
                reports = list(self.data["community_reports"].values())
        reports = sorted(reports, key=lambda r: -r["importance"])
        return {
            "query": theme or "all",
            "communities": reports,
            "synthesis": " | ".join(r["executive_summary"] for r in reports[:4]),
        }

    def fcc_components(self) -> Dict[str, str]:
        """Connected components. Not Leiden. Not GraphRAG."""
        ids = [
            str(e["id"])
            for e in (self.data.get("entities") or [])
            if isinstance(e, dict) and e.get("id")
        ]
        parent = {i: i for i in ids}

        def find(x: str) -> str:
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], x)
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            if a not in parent or b not in parent:
                return
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for rel in self.data.get("relations") or []:
            if isinstance(rel, dict):
                union(str(rel.get("src") or ""), str(rel.get("dst") or ""))
        roots: Dict[str, str] = {}
        n = 0
        out: Dict[str, str] = {}
        for i in ids:
            root = find(i)
            if root not in roots:
                roots[root] = f"fcc_component_{n}"
                n += 1
            out[i] = roots[root]
        return out

    def qfs_search(self, query: str, top_k: int = 8) -> Dict[str, Any]:
        """Map partials per bag, helpfulness reduce. Not Leiden. Not GraphRAG."""
        units = [
            u
            for u in (self.data.get("text_units") or [])
            if isinstance(u, dict) and u.get("valid", True)
        ]
        empty = {
            "query": query,
            "units": [],
            "synthesis": "",
            "bags": 0,
            "partials": [],
        }
        if not units:
            return empty
        q = (query or "").lower()
        q_tokens = [t for t in re.findall(r"[a-z0-9_]{3,}", q)]
        sent_re = re.compile(r"(?<=[.!?])\s+")
        comps = self.fcc_components()
        bags: Dict[str, List[Dict[str, Any]]] = {}
        for unit in units:
            sid = str(unit.get("source_id") or "")
            bag = sid or str(unit.get("community") or "")
            if not bag:
                blob = str(unit.get("text") or "").lower()
                bag = "fcc_orphan"
                for eid, cid in comps.items():
                    title = str((self._by_id.get(eid) or {}).get("title") or eid)
                    if title.lower() in blob:
                        bag = cid
                        break
            bags.setdefault(bag, []).append(unit)
        partials: List[Dict[str, Any]] = []
        for bag_id, group in bags.items():
            sentences: List[Dict[str, Any]] = []
            blob = " ".join(str(u.get("text") or "") for u in group).lower()
            covered = sum(1 for t in q_tokens if t in blob)
            if q and q in blob:
                covered = max(covered, 1)
            help_n = 0
            if q_tokens:
                help_n = int(100 * covered / max(1, len(q_tokens)))
            elif covered:
                help_n = 50
            if covered <= 0:
                help_n = 0
            if help_n <= 0:
                continue
            for unit in group:
                text = str(unit.get("text") or "").strip()
                for sent in sent_re.split(text) or [text]:
                    sent = sent.strip()
                    if len(sent) < 8:
                        continue
                    low = sent.lower()
                    score = sum(1.0 for t in q_tokens if t in low)
                    if q and q in low:
                        score += 3.0
                    if score <= 0:
                        continue
                    sentences.append(
                        {
                            "id": str(unit.get("unit_id") or ""),
                            "title": bag_id,
                            "description": sent[:400],
                            "source": str(
                                unit.get("unit_id") or unit.get("source_id") or ""
                            ),
                            "score": score,
                            "community": bag_id,
                        }
                    )
            if not sentences:
                continue
            sentences.sort(key=lambda r: -float(r.get("score") or 0))
            partials.append(
                {
                    "bag": bag_id,
                    "helpfulness": help_n,
                    "sentences": [s["description"] for s in sentences],
                    "hits": sentences,
                }
            )
        partials.sort(key=lambda p: -int(p.get("helpfulness") or 0))
        picked: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for part in partials:
            for row in part.get("hits") or []:
                key = str(row.get("description") or "")[:80]
                if key in seen:
                    continue
                seen.add(key)
                picked.append(row)
                if len(picked) >= max(1, top_k):
                    break
            if len(picked) >= max(1, top_k):
                break
        synthesis = " ".join(r["description"] for r in picked)
        return {
            "query": query,
            "units": picked,
            "synthesis": synthesis,
            "bags": len(partials),
            "partials": partials,
            "backend": "fcc_qfs",
            "reduce_mode": "extractive",
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.data, indent=indent)

    def export_dict(self) -> Dict[str, Any]:
        return self.data

    def export_delta(self) -> Dict[str, Any]:
        """Persistable slice. Not a full GraphRAG rebuild."""
        sourced = [
            e
            for e in (self.data.get("entities") or [])
            if isinstance(e, dict) and e.get("sources")
        ]
        return {
            "text_units": list(self.data.get("text_units") or []),
            "aliases": dict(self.data.get("aliases") or {}),
            "entities": sourced,
            "relations": [
                r
                for r in (self.data.get("relations") or [])
                if isinstance(r, dict)
                and (
                    r.get("description")
                    and r.get("description") != "co-occurrence"
                )
            ],
            "full_rebuild": False,
        }

    def save_delta(self, path: Any) -> str:
        from pathlib import Path

        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(self.export_delta(), default=str), encoding="utf-8")
        return str(dest)

    def load_delta(self, path: Any) -> Dict[str, Any]:
        from pathlib import Path

        dest = Path(path)
        if not dest.is_file():
            return {"ok": False, "reason": "missing"}
        blob = json.loads(dest.read_text(encoding="utf-8"))
        for unit in blob.get("text_units") or []:
            if isinstance(unit, dict):
                self.ingest_delta([], [], text_unit=unit)
        self.ingest_delta(
            list(blob.get("entities") or []),
            list(blob.get("relations") or []),
        )
        aliases = blob.get("aliases") or {}
        if isinstance(aliases, dict):
            self.data.setdefault("aliases", {}).update(aliases)
        return {
            "ok": True,
            "units": len(self.data.get("text_units") or []),
            "full_rebuild": False,
        }
