"""FlowChartCharter core — execution-and-quality-first multi-agent state-charts."""
from .metrics import ExecutionMetrics
from .agents import Agent, BossAgent, AgentStatus
from .blackboard import Blackboard, TaskRequest
from .charter import FlowUnit, Charter, CharterState
from .system import FlowChartCharterSystem
from .fitness import fitness, DEFAULT_ALPHA, DEFAULT_BETA, DEFAULT_GAMMA, DEFAULT_DELTA, COST_NORM
from .vectors import (
    StrategyVector,
    BudgetVector,
    GovernanceVector,
    OpsVector,
    RhythmAudit,
    validate_executive_payload,
)
from .executive import CEOAgent, CFOAgent, BoardAgent, RhythmValidatorAgent, ExecutiveBoard
from .knowledge_graph import KnowledgeGraph, build_ontology
from .foundations import FOUNDATIONS, foundations_table, blueprint_export, FLOW_UNIT_BLUEPRINT
from .quantum import (
    QuantumRouter,
    quantum_path_select,
    build_superposition,
    measure,
    reinforce,
    entanglement_score,
    contextual_entropy,
    apply_cfo_budget_matrix,
    SuperpositionState,
    PathAmplitude,
    MeasurementRecord,
    DEFAULT_PATHS,
    PATH_STANDARD,
    PATH_CLEANSING,
    PATH_LITE,
)
from .synergy import synergy_score, structural_divergence, handoff_synergy, mean_pair_synergy
from .skills import (
    AgentSkillRuntime,
    MuscleMemoryStore,
    MuscleMemoryRecord,
    RosterAction,
    init_boss_agent,
)
from .prompts import BOSS_AGENT_SYSTEM_PROMPT, BOSS_ACKNOWLEDGEMENT, AGENT_SKILL_SCHEMAS
from .reference_engine import (
    TypedFlowUnit,
    AgentFitness,
    ReferenceQuantumRouter,
    WorkerAgent,
    BossAgent as ReferenceBossAgent,
    CFOHaltError,
    default_playbook,
    run_reference_simulation,
)

__all__ = [
    "ExecutionMetrics",
    "Agent",
    "BossAgent",
    "AgentStatus",
    "Blackboard",
    "TaskRequest",
    "FlowUnit",
    "Charter",
    "CharterState",
    "FlowChartCharterSystem",
    "fitness",
    "COST_NORM",
    "StrategyVector",
    "BudgetVector",
    "GovernanceVector",
    "OpsVector",
    "RhythmAudit",
    "validate_executive_payload",
    "CEOAgent",
    "CFOAgent",
    "BoardAgent",
    "RhythmValidatorAgent",
    "ExecutiveBoard",
    "KnowledgeGraph",
    "build_ontology",
    "FOUNDATIONS",
    "foundations_table",
    "blueprint_export",
    "FLOW_UNIT_BLUEPRINT",
    "QuantumRouter",
    "quantum_path_select",
    "build_superposition",
    "measure",
    "reinforce",
    "entanglement_score",
    "contextual_entropy",
    "apply_cfo_budget_matrix",
    "SuperpositionState",
    "PathAmplitude",
    "MeasurementRecord",
    "DEFAULT_PATHS",
    "PATH_STANDARD",
    "PATH_CLEANSING",
    "PATH_LITE",
    "synergy_score",
    "structural_divergence",
    "handoff_synergy",
    "mean_pair_synergy",
    "AgentSkillRuntime",
    "MuscleMemoryStore",
    "MuscleMemoryRecord",
    "RosterAction",
    "init_boss_agent",
    "BOSS_AGENT_SYSTEM_PROMPT",
    "BOSS_ACKNOWLEDGEMENT",
    "AGENT_SKILL_SCHEMAS",
    "TypedFlowUnit",
    "AgentFitness",
    "ReferenceQuantumRouter",
    "WorkerAgent",
    "ReferenceBossAgent",
    "CFOHaltError",
    "default_playbook",
    "run_reference_simulation",
]
__version__ = "0.6.0"
