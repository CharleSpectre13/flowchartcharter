"""FlowChartCharter Brain 1 — hierarchical knowledge graph (graph-engineering).

GraphRAG remains a *callable sub-flow* for pure relational discovery.
The Charter owns execution; this graph owns durable domain ontology + memory.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set
import json


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
        Entity("fcc", "FlowChartCharter Engineering", "Concept",
               "Execution-and-quality-first multi-agent state-chart systems; agents follow rather than search.",
               "core_concept", 1.0, ["Drive:Blueprint", "Drive:ArchSpec", "IMG:mindmap"]),
        Entity("exec_over_retrieval", "Execution over Retrieval", "Concept",
               "Primary focus is fastest reliable path to completion, not open graph lookup.",
               "core_concept", 0.95, ["Drive:Blueprint", "IMG:playbook"]),
        Entity("deterministic_playbooks", "Deterministic Playbooks", "Concept",
               "Pre-approved paths eliminate guesswork and execution drift.",
               "core_concept", 0.9, ["Drive:HeadCoach"]),
        Entity("unified_multi_agent", "Unified Multi-Agent Architecture", "Concept",
               "Corporate hierarchy + BSP super-steps + Blackboard volunteer binding.",
               "core_concept", 0.9, ["Drive:SystemDesign"]),
        Entity("self_optimizing", "Self-Optimizing System", "Concept",
               "Async RLAIF via Monday Morning Sync raises benchmarks without human micro-management.",
               "core_concept", 0.9, ["Drive:Blueprint"]),
        # Foundational structures
        Entity("charter", "Charter (Pre-drawn Map)", "Structure",
               "Quantum measurement operator M that collapses path superposition into deterministic action.",
               "foundational", 1.0, ["Spreadsheet:Table1", "Drive:ArchSpec"]),
        Entity("flow_units", "Flow Units (Type-safe Contracts)", "Structure",
               "Discrete modules |FlowUnit_i⟩ with explicit I/O and exit criteria.",
               "foundational", 0.95, ["Spreadsheet:Table1"]),
        Entity("rhythm_markers", "Rhythm Markers (Validation Points)", "Structure",
               "Self-auditing checkpoints that force wave-function collapse before Blackboard commit.",
               "foundational", 0.95, ["Spreadsheet:Table1", "IMG:playbook"]),
        Entity("muscle_memory", "Muscle-Memory Loop", "Structure",
               "Historical success amplitudes c_i weight future path selection; autonomous correction.",
               "foundational", 0.95, ["Spreadsheet:Table1"]),
        Entity("engineer_exit", "Engineer Exit / Coach Trust Hand-Off", "Structure",
               "Milestone of Earned Engineering Trust — Head Coach steps back without stepping out.",
               "foundational", 1.0, ["Spreadsheet:Table1", "Drive:HeadCoach"]),
        Entity("monday_sync", "Monday Morning Sync (Async RLAIF)", "Structure",
               "ST-07 downtime talent + prompt optimization under Boss Agent leadership.",
               "foundational", 0.9, ["Spreadsheet:Table1", "IMG:playbook"]),
        # Hierarchy
        Entity("ceo", "CEO Agent", "Role", "Strategic vectors; intervenes only on sync/forks.", "hierarchy", 0.85, ["Drive:Blueprint"]),
        Entity("cfo", "CFO Agent", "Role", "BudgetVector; token spend vs cap; halt_if_over.", "hierarchy", 0.85, ["Drive:Blueprint"]),
        Entity("board", "Executive Board", "Role", "GovernanceVector; approves Coach Trust Hand-Off.", "hierarchy", 0.9, ["Drive:ArchSpec"]),
        Entity("gm", "General Manager (Boss Agent)", "Role", "Day-to-day ops buffer; OpsVector talent outcomes.", "hierarchy", 1.0, ["IMG:playbook"]),
        Entity("position_mgr", "Position Managers", "Role", "Segment oversight of charter sub-flows.", "hierarchy", 0.7, ["Drive:HeadCoach"]),
        Entity("key_players", "Key Players", "Role", "Execute flow units under typed contracts.", "hierarchy", 0.8, ["Drive:HeadCoach"]),
        Entity("coaches", "Coaches and Architects", "Role", "Structural integrity and rhythm optimization.", "hierarchy", 0.75, ["Drive:HeadCoach"]),
        Entity("head_coach", "Human Head Coach", "Role", "System Architect; designs Charter, earns trust exit.", "hierarchy", 1.0, ["Drive:HeadCoach"]),
        Entity("validator", "Rhythm Marker Validator", "Role", "Maker-checker at gates; never the implementor.", "hierarchy", 0.9, ["skill:rhythm-marker-validator"]),
        # Mechanisms
        Entity("blackboard", "Blackboard (Structured Communication)", "Mechanism",
               "JSON performance vectors only — forbids free-form NL among agents.",
               "operations", 0.95, ["Drive:Blueprint"]),
        Entity("talent_mgmt", "Dynamic Talent Management", "Mechanism",
               "Promote / demote / fire by fitness during Monday Morning Sync.",
               "operations", 0.9, ["Drive:Blueprint"]),
        Entity("bsp", "BSP Super-Step Engine", "Mechanism",
               "Pregel-style parallel execution with deterministic channel reducers.",
               "operations", 0.85, ["Drive:SystemDesign"]),
        # Math
        Entity("superposition", "Quantum Path Superposition", "Metric",
               "|ψ⟩ = Σ c_i |FlowUnit_i⟩ with c_i from muscle-memory success rates.",
               "math", 0.95, ["Drive:ArchSpec", "IMG:playbook"]),
        Entity("collapse", "Wave Function Collapse (Measurement)", "Metric",
               "|ExecutedPath⟩ = M|ψ⟩ at Rhythm Markers — 100% confident action.",
               "math", 0.95, ["Drive:ArchSpec"]),
        Entity("fitness_score", "Agent Fitness Score F(x)", "Metric",
               "F = α·(Q_success/Q_total) + β·(1/Δt) − γ·Tokens + Q_entanglement",
               "math", 1.0, ["Drive:Blueprint"]),
        Entity("synergy", "Synergy Entanglement Score", "Metric",
               "How seamlessly agent output integrates into next unit without friction.",
               "math", 0.9, ["Drive:Blueprint"]),
        # Goals
        Entity("earned_trust", "Earned Engineering Trust", "Goal",
               "Empirically proven reliability enabling human-out-of-loop scale.",
               "goals", 1.0, ["Drive:HeadCoach"]),
        Entity("no_micromanage", "Eliminate Micro-management", "Goal",
               "Engineer designs playbook and steps back as Head Coach.",
               "goals", 0.9, ["Drive:HeadCoach"]),
        Entity("latency_cost", "Latency and Cost Reduction", "Goal",
               "First-class metrics; type-safe contracts kill token bloat.",
               "goals", 0.9, ["Drive:ArchSpec"]),
        Entity("scalable_perf", "Scalable Performance", "Goal",
               "Measured by agents-on-charter and human-out-of-loop time.",
               "goals", 0.95, ["Drive:ArchSpec"]),
        # Phases
        Entity("st01", "ST-01 Charter Init", "Phase", "Board + Boss intake; StrategyVector.", "phases", 0.7),
        Entity("st02", "ST-02 Voluntary Bind", "Phase", "Blackboard volunteer capability×rank match.", "phases", 0.7),
        Entity("st03", "ST-03 Super-Step", "Phase", "BSP parallel flow unit execution.", "phases", 0.7),
        Entity("st04", "ST-04 Rhythm Audit", "Phase", "Independent RhythmAudit gate.", "phases", 0.85),
        Entity("st05", "ST-05 Muscle Memory", "Phase", "Remediation from checkpoints (max 3).", "phases", 0.7),
        Entity("st06", "ST-06 Coach Trust", "Phase", "GovernanceVector approve_hand_off.", "phases", 0.9),
        Entity("st07", "ST-07 Monday Sync", "Phase", "Talent + RLAIF downtime optimization.", "phases", 0.85),
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


def _community_reports(entities: List[Entity], relations: List[Relation]) -> Dict[str, Dict[str, Any]]:
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
        self._by_id = {e["id"]: e for e in self.data["entities"]}
        self._out: Dict[str, List[Dict]] = {}
        self._in: Dict[str, List[Dict]] = {}
        for r in self.data["relations"]:
            self._out.setdefault(r["src"], []).append(r)
            self._in.setdefault(r["dst"], []).append(r)

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
            reports = [r for r in reports if t in r["title"].lower() or t in r["executive_summary"].lower()]
            if not reports:
                reports = list(self.data["community_reports"].values())
        reports = sorted(reports, key=lambda r: -r["importance"])
        return {
            "query": theme or "all",
            "communities": reports,
            "synthesis": " | ".join(r["executive_summary"] for r in reports[:4]),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.data, indent=indent)

    def export_dict(self) -> Dict[str, Any]:
        return self.data
