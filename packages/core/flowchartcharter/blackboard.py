from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from .agents import Agent


@dataclass
class TaskRequest:
    id: str
    description: str
    embedding: Dict[str, float]
    claimed_by: Optional[str] = None


@dataclass
class Blackboard:
    active_jobs: List[str] = field(default_factory=list)
    completed_jobs: List[str] = field(default_factory=list)
    tasks: List[TaskRequest] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)

    def post(self, task: TaskRequest) -> None:
        self.tasks.append(task)
        self.logs.append(f"posted:{task.id}")

    def volunteer_bind(self, agents: List[Agent], temperature: float = 1.0) -> Dict[str, str]:
        """Each open task claimed by highest volunteer_score agent."""
        assignments: Dict[str, str] = {}
        available = [a for a in agents if a.status.value in ("Active", "Promoted")]
        for task in self.tasks:
            if task.claimed_by:
                continue
            best: Optional[Agent] = None
            best_score = -1.0
            for a in available:
                if a.id in assignments.values():
                    continue
                s = a.volunteer_score(task.embedding, temperature=temperature)
                if s > best_score:
                    best_score = s
                    best = a
            if best is not None and best_score > 0:
                task.claimed_by = best.id
                assignments[task.id] = best.id
                self.logs.append(f"bound:{task.id}->{best.name}:{best_score:.3f}")
        return assignments
