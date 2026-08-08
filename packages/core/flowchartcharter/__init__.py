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
]
__version__ = "0.2.0"
