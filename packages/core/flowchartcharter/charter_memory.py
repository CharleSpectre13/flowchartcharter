"""Incremental Charter Memory — delta ingest, not a GraphRAG rebuild.

{not kg.full_rebuild}
    ingest_delta(units)
{|entities|' >= |entities| ∧ not kg.full_rebuild ∧ adjacency_ok}

Extractor proposes triples. Verifier is a different function.
claimed_graphrag is never set here.
"""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .knowledge_graph import KnowledgeGraph

TITLE_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9]+(?:[ \t]+[A-Z][A-Za-z0-9]+){0,4})\b"
)
REL_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"(.+?)\s+(?:is|are)\s+(?:an?\s+|the\s+)?(.+)", "is_a"),
    (r"(.+?)\s+uses\s+(.+)", "uses"),
    (r"(.+?)\s+depends on\s+(.+)", "depends_on"),
    (r"(.+?)\s+owns\s+(.+)", "owns"),
    (r"(.+?)\s+implements\s+(.+)", "implements"),
    (r"(.+?)\s+stores\s+(.+)", "stores"),
    (r"(.+?)\s+fails when\s+(.+)", "fails_when"),
    (r"(.+?)\s+delays when\s+(.+)", "delays_when"),
    (r"(.+?)\s+blocks\s+(.+)", "blocks"),
    (r"(.+?)\s+causes\s+(.+)", "causes"),
    (r"(.+?)\s+prevents\s+(.+)", "prevents"),
    (r"(.+?)\s+contains\s+(.+)", "contains"),
)
STOP_TITLES = {
    "the",
    "a",
    "an",
    "this",
    "that",
    "these",
    "those",
    "when",
    "overall",
    "theme",
    "path",
    "charter",
    "quality",
    "trust",
    "and",
    "or",
    "of",
    "to",
    "for",
    "from",
}
QUOTE_RE = re.compile(r"[\"']([A-Za-z][A-Za-z0-9 _-]{2,40})[\"']")
ACRONYM_RE = re.compile(r"\b([A-Z]{2,8})\b")


@dataclass
class TextUnit:
    unit_id: str
    text: str
    source_id: str
    content_hash: str
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProposedGraph:
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    implementor_role: str = "Extractor"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": list(self.entities),
            "relations": list(self.relations),
            "implementor_role": self.implementor_role,
        }


@dataclass
class VerifyVerdict:
    accepted: bool
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]
    issues: List[str]
    auditor_role: str = "Audit Manager"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "entities": list(self.entities),
            "relations": list(self.relations),
            "issues": list(self.issues),
            "auditor_role": self.auditor_role,
        }


@dataclass
class MergeReceipt:
    added: int
    updated: int
    relations_added: int
    entity_count_before: int
    entity_count_after: int
    full_rebuild: bool
    source_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def make_text_unit(text: str, *, source_id: str = "") -> TextUnit:
    blob = (text or "").strip()
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return TextUnit(
        unit_id=f"TU-{uuid.uuid4().hex[:10].upper()}",
        text=blob,
        source_id=source_id or f"src-{digest}",
        content_hash=digest,
        created_at=time.time(),
    )


def stable_id(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", (title or "").lower())
    return slug[:48] or "mem_anon"


def _clean_title(raw: str) -> str:
    t = re.sub(r"\s+", " ", (raw or "").strip(" .:;,\"'"))
    return t[:80]


def extract_triples(
    text: str,
    *,
    source_id: str = "",
    implementor_role: str = "Extractor",
) -> ProposedGraph:
    """Heuristic extract. Not an LLM. Not GraphRAG."""
    entities: Dict[str, Dict[str, Any]] = {}
    relations: List[Dict[str, Any]] = []

    def upsert(title: str) -> str:
        title = _clean_title(title)
        if len(title) < 2 or title.lower() in STOP_TITLES:
            return ""
        eid = stable_id(title)
        if eid not in entities:
            entities[eid] = {
                "id": eid,
                "title": title,
                "type": "Concept",
                "description": f"Extracted from {source_id or 'text'}",
                "community": "fcc_community",
                "importance": 0.55,
                "sources": [source_id] if source_id else [],
            }
        return eid

    for sentence in re.split(r"(?<=[.!?])\s+", text or ""):
        found: List[str] = []
        for match in TITLE_RE.finditer(sentence):
            eid = upsert(match.group(1))
            if eid:
                found.append(eid)
        for match in QUOTE_RE.finditer(sentence):
            eid = upsert(match.group(1))
            if eid:
                found.append(eid)
        for match in ACRONYM_RE.finditer(sentence):
            eid = upsert(match.group(1))
            if eid:
                found.append(eid)
        for pat, rel in REL_PATTERNS:
            m = re.search(pat, sentence, flags=re.I)
            if not m:
                continue
            src = upsert(m.group(1))
            dst = upsert(m.group(2))
            if src and dst and src != dst:
                relations.append(
                    {
                        "src": src,
                        "dst": dst,
                        "type": rel,
                        "description": sentence.strip()[:160],
                        "strength": 0.7,
                    }
                )
        for i, a in enumerate(found):
            for b in found[i + 1:]:
                relations.append(
                    {
                        "src": a,
                        "dst": b,
                        "type": "related_to",
                        "description": "co-occurrence",
                        "strength": 0.4,
                    }
                )
    return ProposedGraph(
        entities=list(entities.values()),
        relations=relations,
        implementor_role=implementor_role,
    )


def verify_extraction(
    proposed: ProposedGraph,
    *,
    existing_ids: Optional[Sequence[str]] = None,
    implementor_role: str = "",
    auditor_role: str = "Audit Manager",
) -> VerifyVerdict:
    """Independent checker. Must not be the extractor."""
    impl = (implementor_role or proposed.implementor_role or "").lower()
    aud = (auditor_role or "").lower()
    issues: List[str] = []
    if impl and aud and impl == aud:
        issues.append("maker_checker_violation")
    known = set(existing_ids or [])
    accepted_e: List[Dict[str, Any]] = []
    ids: set[str] = set(known)
    for ent in proposed.entities:
        eid = str(ent.get("id") or "")
        title = str(ent.get("title") or "").strip()
        if not eid or not title:
            issues.append("entity_missing_id_or_title")
            continue
        accepted_e.append(ent)
        ids.add(eid)
    accepted_r: List[Dict[str, Any]] = []
    for rel in proposed.relations:
        src = str(rel.get("src") or "")
        dst = str(rel.get("dst") or "")
        if src not in ids or dst not in ids:
            issues.append("relation_unresolved")
            continue
        accepted_r.append(rel)
    accepted = (not any(i == "maker_checker_violation" for i in issues)) and (
        bool(accepted_e) or bool(accepted_r)
    )
    if not accepted_e and "empty_extract" not in issues and not accepted:
        if "maker_checker_violation" not in issues:
            issues.append("empty_extract")
    return VerifyVerdict(
        accepted=accepted,
        entities=accepted_e if accepted else [],
        relations=accepted_r if accepted else [],
        issues=issues,
        auditor_role=auditor_role,
    )


def ingest_text(
    kg: KnowledgeGraph,
    text: str,
    *,
    source_id: str = "",
    implementor_role: str = "Extractor",
    auditor_role: str = "Audit Manager",
) -> Dict[str, Any]:
    """Maker-checker ingest of one TextUnit."""
    unit = make_text_unit(text, source_id=source_id)
    proposed = extract_triples(
        unit.text, source_id=unit.source_id, implementor_role=implementor_role
    )
    ents = kg.data.get("entities") or []
    existing = [
        str(e.get("id")) for e in ents if isinstance(e, dict)
    ]
    verdict = verify_extraction(
        proposed,
        existing_ids=existing,
        implementor_role=implementor_role,
        auditor_role=auditor_role,
    )
    receipt: Optional[MergeReceipt] = None
    if verdict.accepted:
        receipt = kg.ingest_delta(
            verdict.entities,
            verdict.relations,
            text_unit=unit.to_dict(),
        )
    return {
        "unit": unit.to_dict(),
        "proposed": proposed.to_dict(),
        "verdict": verdict.to_dict(),
        "merge": receipt.to_dict() if receipt else None,
        "ok": bool(verdict.accepted and receipt is not None),
        "full_rebuild": False,
        "claimed_graphrag": False,
    }


def run_reindex_loop(
    kg: KnowledgeGraph,
    documents: Sequence[Dict[str, str]],
    *,
    max_docs: int = 20,
    implementor_role: str = "Extractor",
    auditor_role: str = "Audit Manager",
) -> Dict[str, Any]:
    """loop-engineer: extract → verify → merge → stop. Cap max_docs."""
    receipts: List[Dict[str, Any]] = []
    for doc in list(documents)[: max(1, int(max_docs))]:
        text = str(doc.get("text") or "")
        if not text.strip():
            continue
        receipts.append(
            ingest_text(
                kg,
                text,
                source_id=str(doc.get("source_id") or ""),
                implementor_role=implementor_role,
                auditor_role=auditor_role,
            )
        )
    added = sum(
        int((r.get("merge") or {}).get("added") or 0) for r in receipts
    )
    return {
        "ok": any(r.get("ok") for r in receipts) or not receipts,
        "docs": len(receipts),
        "added": added,
        "full_rebuild": False,
        "claimed_graphrag": False,
        "receipts": receipts,
    }


def bind_episode(
    kg: KnowledgeGraph,
    *,
    goal: str,
    path: Optional[Sequence[str]] = None,
    quality: float = 0.0,
    trust: bool = False,
    source_id: str = "",
) -> Dict[str, Any]:
    """One charter run → one TextUnit. Extractor ≠ verifier."""
    steps = " → ".join(list(path or [])[:8]) or "path_A"
    text = (
        f"Charter {goal}. Path {steps}. "
        f"Quality {float(quality):.2f}. Trust {bool(trust)}."
    )
    sid = source_id or f"episode:{stable_id(goal)[:32]}"
    out = ingest_text(
        kg,
        text,
        source_id=sid,
        implementor_role="Extractor",
        auditor_role="Audit Manager",
    )
    out["episode"] = True
    return out
