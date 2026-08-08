"""Production integration layer — LLMExecutionClient + Vector DB backends.

Phase 1 Launch Roadmap:
  - LLMExecutionClient: inject playbook constraints + termination_risk_index
  - Production Muscle-Memory backends (in-memory | Qdrant | Pinecone)
  - Pydantic schema gate → entanglement_errors on violation
  - Async fan-out helpers for Boss Agent rhythm (max parallelism, zero idle)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

from pydantic import BaseModel, Field, ValidationError, field_validator

from .llm_bridge import LLMBridge, LLMBridgeConfig, LLMNodeOutput
from .muscle_memory import (
    ExecutionMemoryRecord,
    cosine_similarity,
    encode_state,
)
from .survival import GenerationParameters, generation_params_for_risk


# =============================================================================
# 1. Strict LLM output schema (Boss Agent handoff contract)
# =============================================================================


class FlowUnitResultSchema(BaseModel):
    """Canonical LLM return — any violation → entanglement_errors += 1."""

    result: str = Field(..., min_length=1, max_length=64)
    quality: float = Field(..., ge=0.0, le=1.0)
    path: str = Field(default="path_A")
    tokens: int = Field(..., ge=0, le=1_000_000)
    notes: str = Field(default="", max_length=4000)
    schema_ok: bool = Field(default=True)
    output_payload: Dict[str, Any] = Field(default_factory=dict)
    expected_keys_present: bool = Field(default=True)

    @field_validator("result")
    @classmethod
    def result_token(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("ok", "fail", "partial", "remediate"):
            # coerce free-text "success" style answers
            if v in ("success", "done", "complete", "passed"):
                return "ok"
            if v in ("error", "failed", "broken"):
                return "fail"
            raise ValueError(f"result must be ok|fail|partial|remediate, got {v!r}")
        return v

    @field_validator("path")
    @classmethod
    def path_token(cls, v: str) -> str:
        allowed = {"path_A", "path_B", "path_lite"}
        if v not in allowed:
            raise ValueError(f"path must be one of {allowed}")
        return v

    def to_llm_node_output(self) -> LLMNodeOutput:
        return LLMNodeOutput(
            result=self.result,
            quality=self.quality,
            path=self.path,
            tokens=self.tokens,
            notes=self.notes,
            schema_ok=self.schema_ok and self.expected_keys_present,
        )


class SchemaValidationReport(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    entanglement_increment: int = 0
    raw_excerpt: str = ""


def validate_llm_output(
    raw: Any,
    *,
    expected_output_keys: Optional[Sequence[str]] = None,
) -> Tuple[Optional[FlowUnitResultSchema], SchemaValidationReport]:
    """Strict Pydantic gate. On failure return report with entanglement delta."""
    errors: List[str] = []
    data: Any = raw
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(
                ln for ln in lines if not ln.strip().startswith("```")
            )
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return None, SchemaValidationReport(
                valid=False,
                errors=[f"json_decode: {exc}"],
                entanglement_increment=1,
                raw_excerpt=text[:240],
            )

    if not isinstance(data, dict):
        return None, SchemaValidationReport(
            valid=False,
            errors=["payload is not an object"],
            entanglement_increment=1,
            raw_excerpt=str(raw)[:240],
        )

    # expected key presence for Boss rhythm markers
    if expected_output_keys:
        missing = [k for k in expected_output_keys if k not in data]
        if missing:
            errors.append(f"missing_keys: {missing}")
            data = dict(data)
            data["expected_keys_present"] = False
            data["schema_ok"] = False

    try:
        model = FlowUnitResultSchema.model_validate(data)
    except ValidationError as exc:
        msgs = [e["msg"] for e in exc.errors()]
        return None, SchemaValidationReport(
            valid=False,
            errors=msgs + errors,
            entanglement_increment=1,
            raw_excerpt=json.dumps(data, default=str)[:240],
        )

    if errors:
        # model parsed but missing keys
        return model, SchemaValidationReport(
            valid=False,
            errors=errors,
            entanglement_increment=1,
            raw_excerpt=json.dumps(data, default=str)[:240],
        )
    return model, SchemaValidationReport(valid=True, entanglement_increment=0)


# =============================================================================
# 2. LLMExecutionClient — production WorkerNode outbound
# =============================================================================


@dataclass
class LLMExecutionRequest:
    workload: str
    path: str
    termination_risk_index: float
    system_prompt: str
    playbook_constraints: Sequence[str] = ()
    expected_output_keys: Sequence[str] = ()
    agent_name: str = "worker"
    role: str = "Key Player"


@dataclass
class LLMExecutionResponse:
    ok: bool
    output: Optional[FlowUnitResultSchema]
    validation: SchemaValidationReport
    generation: Dict[str, Any]
    latency_ms: float
    prompt_chars: int
    entanglement_errors_delta: int
    provider: str
    mock: bool


class LLMExecutionClient:
    """Production LLM client for WorkerNode.

    - Appends playbook constraints to the system prompt
    - Injects termination_risk_index (TPC) → alters generation params
    - Validates every return with FlowUnitResultSchema
    - On schema violation: entanglement_errors_delta = 1 (Boss ledger)
    """

    def __init__(
        self,
        bridge: Optional[LLMBridge] = None,
        *,
        config: Optional[LLMBridgeConfig] = None,
    ) -> None:
        self.bridge = bridge or LLMBridge(config or LLMBridgeConfig.from_env())

    def generation_for_risk(self, risk: float) -> GenerationParameters:
        """High risk → temperature→0, schema_lock, capped tokens."""
        return generation_params_for_risk(max(0.0, min(1.0, risk)))

    def build_system_prompt(self, req: LLMExecutionRequest) -> str:
        gen = self.generation_for_risk(req.termination_risk_index)
        constraints = "\n".join(
            f"  - {c}" for c in req.playbook_constraints
        ) or "  - Follow Typed Flow Unit contracts exactly."
        return (
            f"{req.system_prompt}\n\n"
            f"=== FLOWCHARTCHARTER PLAYBOOK CONSTRAINTS ===\n"
            f"{constraints}\n"
            f"=== TELEOLOGICAL PERFORMANCE CONSTRAINT (TPC) ===\n"
            f"termination_risk_index: {req.termination_risk_index:.4f}\n"
            f"survival_generation: temperature={gen.temperature}, "
            f"top_p={gen.top_p}, max_tokens={gen.max_tokens}, "
            f"schema_lock={gen.schema_lock}, "
            f"creativity_cap={gen.creativity_cap}\n"
            f"You are node {req.agent_name} ({req.role}). "
            f"Any schema divergence raises termination risk. "
            f"Respond with JSON only matching:\n"
            f'{{"result":"ok|fail|partial|remediate","quality":0-1,'
            f'"path":"path_A|path_B|path_lite","tokens":int,'
            f'"notes":str,"schema_ok":bool,"output_payload":{{}}}}'
        )

    def execute(self, req: LLMExecutionRequest) -> LLMExecutionResponse:
        """Synchronous production call (safe inside thread pool)."""
        t0 = time.perf_counter()
        gen = self.generation_for_risk(req.termination_risk_index)
        system = self.build_system_prompt(req)
        # Temporarily override bridge max_tokens from TPC
        old_max = self.bridge.config.max_tokens
        self.bridge.config.max_tokens = int(gen.max_tokens)

        try:
            if not self.bridge.live:
                # mock path still goes through schema validation
                raw_node = self.bridge.execute_worker(
                    system_prompt=system,
                    workload=req.workload,
                    path=req.path,
                    termination_risk_index=req.termination_risk_index,
                )
                raw: Any = {
                    "result": raw_node.result,
                    "quality": raw_node.quality,
                    "path": raw_node.path,
                    "tokens": raw_node.tokens,
                    "notes": raw_node.notes,
                    "schema_ok": raw_node.schema_ok,
                    "output_payload": {"mock": True},
                }
                mock = True
            else:
                # live: use bridge chat with TPC system prompt
                user_msg = (
                    f"Workload: {req.workload}\nSelected path: {req.path}\n"
                    f"termination_risk_index={req.termination_risk_index:.4f}"
                )
                raw_text = self.bridge._chat(system, user_msg)  # noqa: SLF001
                raw = raw_text
                mock = False
        finally:
            self.bridge.config.max_tokens = old_max

        model, report = validate_llm_output(
            raw, expected_output_keys=list(req.expected_output_keys) or None
        )
        latency = (time.perf_counter() - t0) * 1000.0
        return LLMExecutionResponse(
            ok=report.valid and model is not None,
            output=model,
            validation=report,
            generation=gen.to_dict(),
            latency_ms=round(latency, 2),
            prompt_chars=len(system),
            entanglement_errors_delta=report.entanglement_increment,
            provider=self.bridge.config.provider,
            mock=mock,
        )


# =============================================================================
# 3. Production Vector DB backends (Qdrant / Pinecone / memory)
# =============================================================================


class EmbeddingProvider:
    """Embed workload JSON → dense vector.

    Default: deterministic local hasher (no network).
    Optional: OpenAI/xAI-compatible embeddings HTTP API.
    """

    def __init__(
        self,
        *,
        dims: int = 64,
        api_key: str = "",
        base_url: str = "",
        model: str = "text-embedding-3-small",
    ) -> None:
        self.dims = dims
        self.api_key = api_key or os.environ.get("FCC_EMBED_API_KEY", "")
        self.base_url = base_url or os.environ.get("FCC_EMBED_BASE_URL", "")
        self.model = model or os.environ.get(
            "FCC_EMBED_MODEL", "text-embedding-3-small"
        )

    def embed(self, payload: Mapping[str, Any]) -> List[float]:
        text = json.dumps(payload, sort_keys=True, default=str)
        if self.api_key and self.base_url:
            try:
                return self._http_embed(text)
            except Exception:  # noqa: BLE001 — fall back local
                pass
        return self._local_embed(text)

    def _local_embed(self, text: str) -> List[float]:
        """Stable pseudo-embedding from SHA buckets (offline-safe)."""
        vec = [0.0] * self.dims
        # multi-hash bag-of-bytes
        data = text.encode("utf-8")
        for i in range(self.dims):
            h = hashlib.sha256(data + i.to_bytes(2, "little")).digest()
            # map first 4 bytes to [-1, 1]
            val = int.from_bytes(h[:4], "big") / 0xFFFFFFFF
            vec[i] = (val * 2.0) - 1.0
        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def _http_embed(self, text: str) -> List[float]:
        url = f"{self.base_url.rstrip('/')}/embeddings"
        body = json.dumps({"model": self.model, "input": text}).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
        emb = payload["data"][0]["embedding"]
        return [float(x) for x in emb]


class VectorBackend(Protocol):
    def upsert(
        self, point_id: str, vector: Sequence[float], payload: Mapping[str, Any]
    ) -> None: ...

    def search(
        self, vector: Sequence[float], *, top_k: int = 5
    ) -> List[Tuple[float, Dict[str, Any]]]: ...


class InMemoryVectorBackend:
    """Default backend — pure Python cosine store."""

    def __init__(self) -> None:
        self.points: Dict[str, Tuple[List[float], Dict[str, Any]]] = {}

    def upsert(
        self, point_id: str, vector: Sequence[float], payload: Mapping[str, Any]
    ) -> None:
        self.points[point_id] = (list(vector), dict(payload))

    def search(
        self, vector: Sequence[float], *, top_k: int = 5
    ) -> List[Tuple[float, Dict[str, Any]]]:
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for _pid, (vec, payload) in self.points.items():
            scored.append((cosine_similarity(vector, vec), payload))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]


class QdrantVectorBackend:
    """Qdrant REST client (no SDK required).

    Env: FCC_QDRANT_URL, FCC_QDRANT_API_KEY, FCC_QDRANT_COLLECTION
    """

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection: Optional[str] = None,
        dims: int = 64,
    ) -> None:
        self.url = (url or os.environ.get("FCC_QDRANT_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("FCC_QDRANT_API_KEY", "")
        self.collection = collection or os.environ.get(
            "FCC_QDRANT_COLLECTION", "flowchartcharter_muscle_memory"
        )
        self.dims = dims
        if self.url:
            self._ensure_collection()

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["api-key"] = self.api_key
        return h

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            headers=self._headers(),
            method=method,
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}

    def _ensure_collection(self) -> None:
        try:
            self._request("GET", f"/collections/{self.collection}")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                return
            try:
                self._request(
                    "PUT",
                    f"/collections/{self.collection}",
                    {
                        "vectors": {
                            "size": self.dims,
                            "distance": "Cosine",
                        }
                    },
                )
            except Exception:  # noqa: BLE001
                pass

    def upsert(
        self, point_id: str, vector: Sequence[float], payload: Mapping[str, Any]
    ) -> None:
        if not self.enabled:
            return
        # Qdrant wants UUID or unsigned int — hash string ids
        try:
            uuid.UUID(point_id)
            pid: Any = point_id
        except ValueError:
            pid = str(uuid.uuid5(uuid.NAMESPACE_URL, point_id))
        self._request(
            "PUT",
            f"/collections/{self.collection}/points?wait=true",
            {
                "points": [
                    {
                        "id": pid,
                        "vector": list(vector),
                        "payload": dict(payload),
                    }
                ]
            },
        )

    def search(
        self, vector: Sequence[float], *, top_k: int = 5
    ) -> List[Tuple[float, Dict[str, Any]]]:
        if not self.enabled:
            return []
        data = self._request(
            "POST",
            f"/collections/{self.collection}/points/search",
            {
                "vector": list(vector),
                "limit": top_k,
                "with_payload": True,
            },
        )
        out: List[Tuple[float, Dict[str, Any]]] = []
        for hit in data.get("result") or []:
            score = float(hit.get("score") or 0.0)
            payload = hit.get("payload") or {}
            out.append((score, payload))
        return out


class PineconeVectorBackend:
    """Pinecone REST client (no SDK required).

    Env: FCC_PINECONE_API_KEY, FCC_PINECONE_HOST
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("FCC_PINECONE_API_KEY", "")
        self.host = (host or os.environ.get("FCC_PINECONE_HOST", "")).rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.host)

    def _headers(self) -> Dict[str, str]:
        return {
            "Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.host}{path}",
            data=data,
            headers=self._headers(),
            method=method,
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}

    def upsert(
        self, point_id: str, vector: Sequence[float], payload: Mapping[str, Any]
    ) -> None:
        if not self.enabled:
            return
        self._request(
            "POST",
            "/vectors/upsert",
            {
                "vectors": [
                    {
                        "id": point_id[:512],
                        "values": list(vector),
                        "metadata": {
                            k: v
                            for k, v in payload.items()
                            if isinstance(v, (str, int, float, bool))
                        },
                    }
                ]
            },
        )

    def search(
        self, vector: Sequence[float], *, top_k: int = 5
    ) -> List[Tuple[float, Dict[str, Any]]]:
        if not self.enabled:
            return []
        data = self._request(
            "POST",
            "/query",
            {
                "vector": list(vector),
                "topK": top_k,
                "includeMetadata": True,
            },
        )
        out: List[Tuple[float, Dict[str, Any]]] = []
        for match in data.get("matches") or []:
            score = float(match.get("score") or 0.0)
            meta = match.get("metadata") or {}
            # recover nested payload if stored as JSON string
            if "record_json" in meta:
                try:
                    meta = json.loads(meta["record_json"])
                except json.JSONDecodeError:
                    pass
            out.append((score, meta))
        return out


def build_vector_backend(
    *,
    dims: int = 64,
    prefer: Optional[str] = None,
) -> Tuple[str, Any]:
    """Factory: prefer env backend, else in-memory."""
    prefer = (prefer or os.environ.get("FCC_VECTOR_BACKEND", "auto")).lower()
    if prefer in ("qdrant", "auto"):
        q = QdrantVectorBackend(dims=dims)
        if q.enabled:
            return "qdrant", q
    if prefer in ("pinecone", "auto"):
        p = PineconeVectorBackend()
        if p.enabled:
            return "pinecone", p
    return "memory", InMemoryVectorBackend()


@dataclass
class ProductionMuscleMemory:
    """Muscle-Memory Vector DB with production backend + embeddings.

    - embed(workload JSON) via EmbeddingProvider
    - upsert/query against Qdrant | Pinecone | in-memory
    - still exposes classic query_muscle_memory API surface
    """

    backend_name: str = "memory"
    backend: Any = field(default_factory=InMemoryVectorBackend)
    embedder: EmbeddingProvider = field(default_factory=EmbeddingProvider)
    storage: List[ExecutionMemoryRecord] = field(default_factory=list)
    quiet: bool = True
    hits: int = 0
    misses: int = 0
    # dual-write: keep local records for fitness of offline demos
    dual_write_local: bool = True

    @classmethod
    def from_env(cls, *, quiet: bool = True, dims: int = 64) -> "ProductionMuscleMemory":
        name, backend = build_vector_backend(dims=dims)
        return cls(
            backend_name=name,
            backend=backend,
            embedder=EmbeddingProvider(dims=dims),
            quiet=quiet,
        )

    def encode_state(self, data_payload: Mapping[str, Any]) -> List[float]:
        return encode_state(data_payload)

    def embed_workload(self, payload: Mapping[str, Any]) -> List[float]:
        return self.embedder.embed(payload)

    def commit_memory(self, record: ExecutionMemoryRecord) -> None:
        if record.quality < 0.90 and record.entanglement_score < 0.85:
            return
        if self.dual_write_local:
            self.storage.append(record)
        vec = self.embed_workload(
            {
                "job_type": record.job_type,
                "flow_path": record.successful_flow_path,
                "state_vector": record.state_vector,
                "tags": list(record.tags),
            }
        )
        payload = record.to_dict()
        payload["record_json"] = json.dumps(payload, default=str)
        self.backend.upsert(record.memory_id, vec, payload)
        if not self.quiet:
            print(
                f"[Muscle-Memory/{self.backend_name}] committed "
                f"{record.memory_id}"
            )

    def query_muscle_memory(
        self,
        current_payload: Mapping[str, Any],
        similarity_threshold: float = 0.85,
        *,
        state_vector: Optional[Sequence[float]] = None,
        top_k: int = 5,
    ) -> Optional[ExecutionMemoryRecord]:
        """Embed → nearest Flow Path payload from production vector DB."""
        job = str(
            current_payload.get("task")
            or current_payload.get("job")
            or current_payload.get("workload")
            or current_payload.get("job_type")
            or ""
        )
        cur_state = (
            list(state_vector)
            if state_vector is not None
            else self.encode_state(current_payload)
        )
        # Same feature packing as commit_memory for embedding alignment
        query_vec = self.embed_workload(
            {
                "job_type": job,
                "flow_path": current_payload.get("flow_path") or [],
                "state_vector": cur_state,
                "tags": list(current_payload.get("tags") or []),
            }
        )
        hits = list(self.backend.search(query_vec, top_k=top_k))

        # Hybrid: classic state-vector cosine + job_type lexical boost
        if self.storage:
            job_l = job.lower()
            for rec in self.storage:
                score = cosine_similarity(cur_state, rec.state_vector)
                if job_l and job_l in rec.job_type.lower():
                    score = max(score, 0.92)
                elif job_l and rec.job_type.lower() in job_l:
                    score = max(score, 0.88)
                hits.append((score, rec.to_dict()))

        if not hits:
            self.misses += 1
            return None

        hits.sort(key=lambda x: x[0], reverse=True)
        best_score, best_payload = hits[0]
        if best_score < similarity_threshold:
            self.misses += 1
            return None

        self.hits += 1
        return self._payload_to_record(best_payload)

    def _payload_to_record(
        self, payload: Mapping[str, Any]
    ) -> ExecutionMemoryRecord:
        if "record_json" in payload and isinstance(payload["record_json"], str):
            try:
                payload = json.loads(payload["record_json"])
            except json.JSONDecodeError:
                pass
        tags = payload.get("tags") or ()
        if isinstance(tags, list):
            tags = tuple(tags)
        return ExecutionMemoryRecord(
            memory_id=str(payload.get("memory_id") or f"MEM-{uuid.uuid4().hex[:8]}"),
            job_type=str(payload.get("job_type") or "unknown"),
            state_vector=list(payload.get("state_vector") or [0.5, 0.5, 1.0, 0.1]),
            successful_flow_path=list(
                payload.get("successful_flow_path") or ["path_A"]
            ),
            entanglement_score=float(payload.get("entanglement_score") or 0.9),
            prompt_tweak=str(payload.get("prompt_tweak") or ""),
            quality=float(payload.get("quality") or 0.9),
            token_cost=int(payload.get("token_cost") or 0),
            tags=tags,
        )

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        return {
            "backend": self.backend_name,
            "records": len(self.storage),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": (self.hits / total) if total else 0.0,
        }

    def export_dict(self) -> Dict[str, Any]:
        return {
            "stats": self.stats(),
            "records": [r.to_dict() for r in self.storage[-50:]],
        }


# =============================================================================
# 4. Async Boss routing — maximum rhythm, minimal idle latency
# =============================================================================


@dataclass
class WorkerTask:
    """Unit of work for parallel fan-out inside a super-step."""

    agent_name: str
    workload: str
    path: str
    system_prompt: str
    termination_risk_index: float
    playbook_constraints: Tuple[str, ...] = ()
    expected_output_keys: Tuple[str, ...] = ()
    role: str = "Key Player"


@dataclass
class WorkerTaskResult:
    agent_name: str
    response: LLMExecutionResponse
    wall_ms: float


def run_workers_parallel(
    tasks: Sequence[WorkerTask],
    *,
    client: Optional[LLMExecutionClient] = None,
    max_workers: Optional[int] = None,
) -> List[WorkerTaskResult]:
    """Fan-out LLMExecutionClient calls without blocking the Boss rhythm.

    Design notes (audit):
      - Super-step barrier: all workers in the BSP step fire concurrently
      - ThreadPoolExecutor: I/O-bound LLM HTTP waits do not serialize
      - max_workers defaults to min(32, n_tasks) — preserves token budget
        visibility at the CFO gate *before* fan-out (call site must pre-gate)
      - Results return in completion order; Boss reorders by agent_name
      - Schema failures already encode entanglement_errors_delta — no extra
        round trip before ledger commit
    """
    if not tasks:
        return []
    client = client or LLMExecutionClient()
    n = len(tasks)
    workers = max_workers or min(32, max(1, n))
    results: List[WorkerTaskResult] = []

    def _run(task: WorkerTask) -> WorkerTaskResult:
        t0 = time.perf_counter()
        resp = client.execute(
            LLMExecutionRequest(
                workload=task.workload,
                path=task.path,
                termination_risk_index=task.termination_risk_index,
                system_prompt=task.system_prompt,
                playbook_constraints=task.playbook_constraints,
                expected_output_keys=task.expected_output_keys,
                agent_name=task.agent_name,
                role=task.role,
            )
        )
        return WorkerTaskResult(
            agent_name=task.agent_name,
            response=resp,
            wall_ms=round((time.perf_counter() - t0) * 1000.0, 2),
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_run, t): t for t in tasks}
        for fut in as_completed(futs):
            results.append(fut.result())
    return results


def apply_execution_to_agent(agent: Any, result: WorkerTaskResult) -> None:
    """Commit LLMExecutionResponse into agent telemetry + entanglement ledger."""
    resp = result.response
    delta = resp.entanglement_errors_delta
    if delta:
        # direct ledger pressure
        agent.record_cycle(
            schema_divergence=delta,
            token_spend=0,
            token_ceiling=0,
            delta_t=resp.latency_ms / 1000.0,
            structural_drift=0.5,
            quality=0.0,
            path="",
            notes="schema_validation_fail",
        )
    if resp.output is not None:
        from .metrics import ExecutionMetrics

        m = ExecutionMetrics(
            token_cost=resp.output.tokens,
            execution_time=max(0.001, resp.latency_ms / 1000.0),
            quality_score=resp.output.quality if resp.ok else min(
                resp.output.quality, 0.5
            ),
            synergy_score=1.0 if resp.ok else 0.5,
            expected_token_cost=resp.output.tokens,
            expected_time=max(0.001, resp.latency_ms / 1000.0),
        )
        agent.history.append(m)
        agent.record_cycle(
            schema_divergence=0 if resp.ok else 1,
            token_spend=resp.output.tokens,
            token_ceiling=max(resp.output.tokens, 1),
            delta_t=m.execution_time,
            structural_drift=0.0 if resp.ok else 0.4,
            quality=m.quality_score,
            path=resp.output.path,
            notes=resp.output.notes[:80],
        )


# Convenience: structure for system.py super-step
def build_superstep_plan(
    *,
    agents: Sequence[Any],
    workload: str,
    path_by_agent: Mapping[str, str],
    playbook_constraints: Sequence[str],
    is_ops: Callable[[Any], bool],
) -> List[WorkerTask]:
    tasks: List[WorkerTask] = []
    for agent in agents:
        if not is_ops(agent):
            continue
        tasks.append(
            WorkerTask(
                agent_name=agent.name,
                workload=workload,
                path=path_by_agent.get(agent.name, "path_A"),
                system_prompt=agent.system_prompt,
                termination_risk_index=agent.termination_risk_index,
                playbook_constraints=tuple(playbook_constraints),
                expected_output_keys=("result", "quality", "path", "tokens"),
                role=agent.role,
            )
        )
    return tasks
