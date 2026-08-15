"""Personal house — drip memory, first day, world-mouth tool.

Never strands: day one has a starter notebook and a phone to Grok
that may be unplugged. GraphRAG is not claimed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .live_model import LiveModel
from .starter_house import STARTER_CHARTER, STARTER_DOCS, starter_seeded


def seed_starter_house(system: Any) -> Dict[str, Any]:
    from .charter_memory import ingest_text

    if starter_seeded(system.knowledge):
        units = (system.knowledge.data or {}).get("text_units") or []
        return {"ok": True, "seeded": False, "text_units": len(units)}
    added = 0
    for doc in STARTER_DOCS:
        ingest_text(system.knowledge, doc["text"], source_id=doc["source_id"])
        added += 1
    units = (system.knowledge.data or {}).get("text_units") or []
    return {"ok": True, "seeded": True, "added": added, "text_units": len(units)}


def shelves(system: Any, model: Optional[LiveModel] = None) -> Dict[str, Any]:
    brain = model or LiveModel.from_env()
    st = brain.status()
    provider = str(st.get("provider") or "mock")
    if st.get("live") and provider == "xai":
        mouth = "grok_http"
    elif st.get("live") and provider == "ollama":
        mouth = "local_llm"
    elif st.get("live"):
        mouth = f"{provider}_http"
    else:
        mouth = "none"
    units = (getattr(system.knowledge, "data", {}) or {}).get("text_units") or []
    return {
        "world_mouth": mouth,
        "house_notebook": "fcc_units",
        "text_units": len(units),
        "claimed_graphrag": False,
        "live": bool(st.get("live")),
        "provider": provider,
        "model": st.get("model"),
    }


def remember(system: Any, text: str, *, source_id: str = "") -> Dict[str, Any]:
    """Drip one note into the house. No corpus required."""
    from .charter_memory import ingest_text

    blob = (text or "").strip()
    if not blob:
        return {"ok": False, "reason": "empty"}
    n = len((system.knowledge.data or {}).get("text_units") or [])
    sid = source_id or f"remember-{n + 1}"
    rec = ingest_text(system.knowledge, blob, source_id=sid)
    rec["ok"] = True
    rec["source_id"] = sid
    rec["claimed_graphrag"] = False
    return rec


def ask_world(prompt: str, *, model: Optional[LiveModel] = None) -> Dict[str, Any]:
    """Call the world mouth inside the harness contract. Never loops."""
    brain = model or LiveModel.from_env()
    st = brain.status()
    out = brain.complete(prompt, max_tokens=256)
    if st.get("live") and st.get("provider") == "xai":
        shelf = "grok_http"
    elif st.get("live") and st.get("provider") == "ollama":
        shelf = "local_llm"
    elif st.get("live"):
        shelf = f"{st.get('provider')}_http"
    else:
        shelf = "none"
    out["shelf"] = shelf
    out["claimed_graphrag"] = False
    return out


def first_day(system: Any) -> Dict[str, Any]:
    """Seed welcome notes, walk the starter charter, issue a receipt."""
    seed = seed_starter_house(system)
    result = system.execute_charter(STARTER_CHARTER)
    receipt = system.issue_stranger_receipt()
    return {
        "ok": True,
        "charter": STARTER_CHARTER,
        "seed": seed,
        "quality": result.get("quality"),
        "trust": result.get("trust"),
        "halted": bool(result.get("halted")),
        "shelves": shelves(system),
        "receipt": receipt,
        "claimed_graphrag": False,
    }


def verify_receipt_path(path: str) -> Dict[str, Any]:
    """Offline stranger check. No vendor. JSON or JSONL."""
    from .stranger_receipt import verify_chain, verify_receipt
    import json

    p = Path(path)
    if not p.is_file():
        return {"ok": False, "reason": "missing"}
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return {"ok": False, "reason": "empty"}
    if raw.startswith("["):
        blob = json.loads(raw)
        ok = verify_chain(blob) if isinstance(blob, list) else verify_receipt(blob)
        return {"ok": bool(ok), "n": len(blob) if isinstance(blob, list) else 1}
    if "\n{" in raw or raw.count("\n") > 0 and not raw.startswith("{"):
        recs = [json.loads(line) for line in raw.splitlines() if line.strip()]
        return {"ok": verify_chain(recs), "n": len(recs)}
    return {"ok": verify_receipt(json.loads(raw)), "n": 1}
