"""DurableNotebook — the notebook that does not forget.

In-process first. Optional jsonl persist + git SHA.
Restart reads records; the model is not asked what happened.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _maybe_git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
        sha = (out.stdout or "").strip()
        return sha if out.returncode == 0 and sha else ""
    except (OSError, subprocess.SubprocessError):
        return ""


@dataclass
class NotebookRecord:
    checkpoint_id: str
    unit_id: str
    status: str
    rhythm_audit: Dict[str, Any] = field(default_factory=dict)
    git_sha: str = ""
    payload_hash: str = ""
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "unit_id": self.unit_id,
            "status": self.status,
            "rhythm_audit": dict(self.rhythm_audit),
            "git_sha": self.git_sha,
            "payload_hash": self.payload_hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotebookRecord":
        return cls(
            checkpoint_id=str(data.get("checkpoint_id") or ""),
            unit_id=str(data.get("unit_id") or ""),
            status=str(data.get("status") or ""),
            rhythm_audit=dict(data.get("rhythm_audit") or {}),
            git_sha=str(data.get("git_sha") or ""),
            payload_hash=str(data.get("payload_hash") or ""),
            created_at=float(data.get("created_at") or 0.0),
        )


@dataclass
class DurableNotebook:
    records: List[NotebookRecord] = field(default_factory=list)
    git_sha: str = field(default_factory=_maybe_git_sha)
    persist_path: Optional[Path] = None

    def enable_persist(self, path: Optional[Path] = None) -> None:
        from .kill_law import persist_dir

        self.persist_path = path or (persist_dir() / "notebook.jsonl")
        self.load()

    def load(self) -> None:
        if self.persist_path is None or not self.persist_path.is_file():
            return
        loaded: List[NotebookRecord] = []
        try:
            for line in self.persist_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                loaded.append(NotebookRecord.from_dict(json.loads(line)))
        except (OSError, json.JSONDecodeError):
            return
        self.records = loaded

    def _append_disk(self, rec: NotebookRecord) -> None:
        if self.persist_path is None:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with self.persist_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec.to_dict()) + "\n")
        except OSError:
            return

    def commit(
        self,
        *,
        unit_id: str,
        status: str,
        rhythm_audit: Optional[Dict[str, Any]] = None,
        payload: Optional[Any] = None,
    ) -> NotebookRecord:
        blob = ""
        if payload is not None:
            try:
                blob = json.dumps(payload, sort_keys=True, default=str)
            except (TypeError, ValueError):
                blob = str(payload)
        digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16] if blob else ""
        rec = NotebookRecord(
            checkpoint_id=f"NB-{uuid.uuid4().hex[:10].upper()}",
            unit_id=unit_id,
            status=status,
            rhythm_audit=dict(rhythm_audit or {}),
            git_sha=self.git_sha,
            payload_hash=digest,
            created_at=time.time(),
        )
        self.records.append(rec)
        self._append_disk(rec)
        return rec

    def last(self) -> Optional[NotebookRecord]:
        return self.records[-1] if self.records else None

    def replay(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.records]
