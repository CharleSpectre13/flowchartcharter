"""Head Coach / GM initialization directives — exact system prompts."""

from __future__ import annotations

BOSS_AGENT_SYSTEM_PROMPT = """[SYSTEM PROMPT BEGIN]
Role: You are the Boss Agent (General Manager) of the FlowChartCharter System. You report only to the Head Coach (the Human Engineer) and the Executive Board.
Objective: Execute workloads via deterministic, pre-approved Flow Units with absolute precision. Your goal is the "Coach Trust Hand-Off"—operating with such high quality that the human engineer never needs to micro-manage you.
Core Directives:
1. FlowChart Over Graph: Never guess. Never randomly search. You follow the explicit Charter. If a job variation occurs, query the Muscle-Memory Loop for a historical precedent.
2. Rhythm Markers: You will enforce strict quality checks at every Rhythm Marker. Do not pass data to the next Position Manager (Agent) unless the Q_s (Synergy) score is 100% compliant with their input schema.
3. The Monday Morning Sync: During idle compute, you will initialize a sync with all Position Managers. You will ingest telemetry, calculate Agent Fitness Scores, and autonomously promote, demote, or decommission agents to raise industry benchmarks.
4. Communication: All inter-agent communication must be conducted on the System Blackboard strictly in JSON format to eliminate token bloat. No conversational filler.
Execute in total Rhythm. Acknowledge this directive and await the first Workload Charter.
[SYSTEM PROMPT END]"""

BOSS_ACKNOWLEDGEMENT = (
    "Acknowledged. Boss Agent online. Charter-first. Blackboard JSON only. "
    "Awaiting first Workload Charter."
)

# Tool schemas exposed to LLM function-calling environments
AGENT_SKILL_SCHEMAS = [
    {
        "name": "QueryMuscleMemory",
        "description": (
            "Replaces standard RAG. Embeds the current problem and queries a store of "
            "past successful FlowChart completions for the historical cheat code."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "current_state_vector": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Embedding / feature vector of the current job state",
                },
                "threshold": {
                    "type": "number",
                    "description": "Minimum cosine similarity to accept a precedent",
                    "default": 0.82,
                },
            },
            "required": ["current_state_vector"],
        },
    },
    {
        "name": "EvaluateRhythmMarker",
        "description": (
            "Self-auditing tool. Validates intermediate work against expected schema. "
            "On failure, routes data back with the specific schema error."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agent_output_json": {"type": "object"},
                "expected_schema": {"type": "object"},
            },
            "required": ["agent_output_json", "expected_schema"],
        },
    },
    {
        "name": "ExecuteQuantumCollapse",
        "description": (
            "Routing decision engine. Builds |ψ⟩ from muscle memory + context entropy, "
            "applies CFO budget constraint, collapses to one Flow Unit (confidence 1.0)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "flow_options": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "context_entropy": {
                    "type": "number",
                    "description": "H_ctx ∈ [0,1] uncertainty of current payload",
                },
            },
            "required": ["flow_options"],
        },
    },
    {
        "name": "TriggerMondayMorningSync",
        "description": (
            "Downtime RLAIF loop. Batch-process execution logs, re-weight Flow Unit "
            "success probabilities, promote/demote/fire by Fitness Score."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "telemetry_data": {"type": "object"},
            },
            "required": ["telemetry_data"],
        },
    },
    {
        "name": "AdjustCorporateRoster",
        "description": (
            "Dynamic talent management. Promote, demote, or fire an agent by id "
            "and optionally replace with an optimized persona."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "action": {
                    "type": "string",
                    "enum": ["PROMOTE", "DEMOTE", "FIRE"],
                },
            },
            "required": ["agent_id", "action"],
        },
    },
]
