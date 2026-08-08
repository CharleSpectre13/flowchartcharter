from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from .agents import Agent
from .vectors import ExecutiveVector, validate_executive_payload


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
    executive_vectors: List[Dict[str, Any]] = field(default_factory=list)

    def post(self, task: TaskRequest) -> None:
        self.tasks.append(task)
        self.logs.append(f"posted:{task.id}")

    def post_vector(self, vec: Union[ExecutiveVector, Dict[str, Any]]) -> bool:
        """Accept only strict executive / rhythm vectors — reject free-form payloads."""
        payload = vec.to_dict() if hasattr(vec, "to_dict") else dict(vec)
        if not validate_executive_payload(payload):
            self.logs.append(f"rejected:invalid-vector:{payload.get('type')}")
            return False
        self.executive_vectors.append(payload)
        self.logs.append(
            f"vector:{payload.get('type')}:{payload.get('charter_id') or payload.get('marker')}"
        )
        return True

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

    def recent_vectors(self, n: int = 12) -> List[Dict[str, Any]]:
        return list(self.executive_vectors[-n:])
