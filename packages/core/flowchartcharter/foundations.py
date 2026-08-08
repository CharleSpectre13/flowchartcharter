"""Five (+1) Foundational Structures — spreadsheet + Arch Spec DNA."""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass(frozen=True)
class FoundationalStructure:
    id: str
    name: str
    description: str
    operational_mechanism: str
    hierarchy_role: str
    performance_metric: str
    rhythm_goal: str
    sources: str


FOUNDATIONS: List[FoundationalStructure] = [
    FoundationalStructure(
        id="charter",
        name="Charter",
        description=(
            "Deterministic playbook and pre-approved map that replaces open-ended "
            "GraphRAG models with sequential primary paths."
        ),
        operational_mechanism=(
            "Acts as quantum measurement operator (M) that collapses agent path "
            "superposition into 100% confident, deterministic actions."
        ),
        hierarchy_role="Executive Board (CEO, CFO, Board) / Head Coach",
        performance_metric=(
            "Path Execution Accuracy (α-weighted); Hallucination Reduction; "
            "Determinism Confidence Score (1.0)."
        ),
        rhythm_goal=(
            "Sets the tone and provides a cheat-sheet blueprint so all agents "
            "move in unison toward a common goal."
        ),
        sources="Drive:ArchSpec, Spreadsheet, IMG:mindmap",
    ),
    FoundationalStructure(
        id="flow_units",
        name="Flow Units",
        description=(
            "Discrete, type-safe work modules and pre-approved components that "
            "serve as the building blocks of the execution map."
        ),
        operational_mechanism=(
            "Enforces explicit inputs, outputs, and exit criteria; modeled as "
            "quantum states |FlowUnit_i⟩ selected via historical success amplitudes c_i."
        ),
        hierarchy_role="General Manager (Boss Agent) / Operations",
        performance_metric=(
            "Token Efficiency (β-weighted cost reduction); "
            "Flow Unit Success Rate (Q_success / Q_total)."
        ),
        rhythm_goal=("Well-oiled machine effect: modular chunks with zero micro-management."),
        sources="Drive:ArchSpec, Spreadsheet, IMG:playbook",
    ),
    FoundationalStructure(
        id="rhythm_markers",
        name="Rhythm Markers",
        description=(
            "Structural evaluation checkpoints and trigger-based measurement events "
            "used to review state snapshots against quality thresholds."
        ),
        operational_mechanism=(
            "Self-auditing via shared Blackboard; validators force collapse of the "
            "wave function before commit."
        ),
        hierarchy_role="Position Managers, Key Players, CFO (Resource Auditor)",
        performance_metric=(
            "Quality Threshold Pass Rate (γ-weighted reliability); " "Time Delta Efficiency (1/Δt)."
        ),
        rhythm_goal=("Facilitates entanglement and synchronizes agent actions before commit."),
        sources="Spreadsheet, skill:rhythm-marker-validator",
    ),
    FoundationalStructure(
        id="muscle_memory",
        name="Muscle-Memory Loop",
        description=(
            "Engineered autonomy feature and historical success database used to "
            "weight future agent decisions."
        ),
        operational_mechanism=(
            "Query historic state checkpoints; feed success rates back into "
            "probability amplitudes to adjust path strategies autonomously."
        ),
        hierarchy_role="Coaches and Boss Agents",
        performance_metric=(
            "Autonomous Correction Rate (human-out-of-loop ratio); "
            "Entanglement Synergy Score (Q_entanglement)."
        ),
        rhythm_goal=("Viral Dance effect: high-speed execution from previous job experience."),
        sources="Drive:Blueprint, Spreadsheet",
    ),
    FoundationalStructure(
        id="coach_trust",
        name="Engineer Exit / Coach Trust Hand-Off",
        description=(
            "Milestone representing transition from human oversight to earned "
            "engineering trust based on proven deterministic reliability."
        ),
        operational_mechanism=(
            "Shift from manual approval loops to asynchronous "
            "'Trust me coach, we got this' — architect acts as Head Coach."
        ),
        hierarchy_role="Human Head Coach / System Architect",
        performance_metric=(
            "Earned Trust Coefficient (reduction in supervisor intervention); "
            "Token Cost Weight (γ)."
        ),
        rhythm_goal=("Empowers the team to execute seamlessly without being overcorrected."),
        sources="Drive:HeadCoach, Spreadsheet, IMG:playbook",
    ),
    FoundationalStructure(
        id="monday_sync",
        name="Monday Morning Sync",
        description=(
            "Downtime team meetings (ST-07) for aligning dynamics, prompt "
            "optimization, and industry benchmarks — async RLAIF."
        ),
        operational_mechanism=(
            "Boss Agent leads telemetry review and dynamic talent management "
            "during low workload."
        ),
        hierarchy_role="Boss Agent / General Manager",
        performance_metric="Promotion/Demotion Velocity (optimization rate in downtime).",
        rhythm_goal=("Raises the bar through structured communication during system downtime."),
        sources="Spreadsheet, Drive:Blueprint, IMG:playbook",
    ),
]


FLOW_UNIT_BLUEPRINT = [
    {
        "element": "RHYTHM MARKER",
        "function": "Self-Auditing Milestone",
        "contract": "State Snapshot",
    },
    {
        "element": "BLACKBOARD",
        "function": "Shared Team Workspace",
        "contract": "Structured JSON",
    },
    {
        "element": "MUSCLE-MEMORY",
        "function": "Historic Optimization",
        "contract": "Success Vector",
    },
]


CORPORATE_LADDER = [
    {"tier": 0, "role": "CEO Agent", "count": 1, "layer": "exec"},
    {"tier": 1, "role": "CFO Agent", "count": 1, "layer": "exec"},
    {"tier": 1, "role": "Executive Board", "count": 1, "layer": "exec"},
    {"tier": 2, "role": "General Manager (Boss)", "count": 1, "layer": "ops"},
    {"tier": 3, "role": "Position Managers", "count": "N", "layer": "ops"},
    {"tier": 4, "role": "Key Players", "count": "N", "layer": "ops"},
    {"tier": 4, "role": "Rhythm Validators", "count": "N", "layer": "audit"},
    {"tier": 5, "role": "Human Head Coach", "count": 1, "layer": "human"},
]


def foundations_table() -> List[Dict[str, Any]]:
    return [asdict(f) for f in FOUNDATIONS]


def blueprint_export() -> Dict[str, Any]:
    return {
        "foundations": foundations_table(),
        "flow_unit_blueprint": FLOW_UNIT_BLUEPRINT,
        "corporate_ladder": CORPORATE_LADDER,
        "fitness_equation": (
            "F(x) = α·(Q_success/Q_total) + β·(1/Δt) − γ·ΣTokens + Q_entanglement"
        ),
        "quantum": {
            "superposition": "|ψ⟩ = Σ c_i |FlowUnit_i⟩",
            "measurement": "|ExecutedPath⟩ = M|ψ⟩",
            "note": "c_i = historical success amplitude from Muscle-Memory Loop",
        },
    }
