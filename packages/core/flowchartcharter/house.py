"""Personal house — durable notebook, first day, world-mouth ActionUnit."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .live_model import LiveModel
from .starter_house import STARTER_CHARTER, STARTER_DOCS, starter_seeded


def house_enabled() -> bool:
    if os.environ.get("FCC_HARNESS_PERSIST") == "0":
        return False
    if (os.environ.get("FCC_HOUSE_PATH") or "").strip():
        return True
    return os.environ.get("FCC_HARNESS_PERSIST") == "1"


def starter_on() -> bool:
    return os.environ.get("FCC_STARTER_HOUSE", "1") != "0"


def house_path() -> Path:
    raw = (os.environ.get("FCC_HOUSE_PATH") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    from .kill_law import persist_dir

    return persist_dir() / "house.jsonl"


def _append(row: Dict[str, Any]) -> None:
    if not house_enabled():
        return
    path = house_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def load_house(system: Any) -> int:
    if not house_enabled():
        return 0
    path = house_path()
    if not path.is_file():
        return 0
    from .charter_memory import ingest_text

    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") == "note" and row.get("text"):
            rec = ingest_text(
                system.knowledge,
                str(row["text"]),
                source_id=str(row.get("source_id") or f"house-{n}"),
            )
            if rec.get("merge") is None:
                system.knowledge.append_text_unit(rec["unit"])
            n += 1
        elif row.get("kind") == "receipt":
            system.last_receipt = row
    return n


def open_house(system: Any) -> Dict[str, Any]:
    """Load file. Seed welcome notes once if the attic is empty."""
    loaded = load_house(system)
    seeded = False
    if house_enabled() and starter_on() and not starter_seeded(system.knowledge):
        seed = seed_starter_house(system)
        seeded = bool(seed.get("seeded"))
        if seeded:
            for doc in STARTER_DOCS:
                _append({"kind": "note", **doc})
    return {"loaded": loaded, "seeded": seeded}


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
        "house_file": str(house_path()) if house_enabled() else "",
    }


def remember(system: Any, text: str, *, source_id: str = "") -> Dict[str, Any]:
    from .charter_memory import ingest_text

    blob = (text or "").strip()
    if not blob:
        return {"ok": False, "reason": "empty"}
    n = len((system.knowledge.data or {}).get("text_units") or [])
    sid = source_id or f"remember-{n + 1}"
    rec = ingest_text(system.knowledge, blob, source_id=sid)
    if rec.get("merge") is None:
        system.knowledge.append_text_unit(rec["unit"])
    rec["ok"] = True
    rec["source_id"] = sid
    rec["claimed_graphrag"] = False
    _append({"kind": "note", "source_id": sid, "text": blob})
    return rec


def ask_world(prompt: str, *, model: Optional[LiveModel] = None) -> Dict[str, Any]:
    """World mouth only through ActionUnit (Halt + schema + cap)."""
    from .action_units import ActionUnit_WorldMouth

    unit = ActionUnit_WorldMouth()
    unit.dry_run = False
    result = unit.execute({"prompt": (prompt or "")[:4000], "max_tokens": 256})
    err = result.error or ""
    if result.blocked:
        return {
            "ok": False,
            "live": False,
            "text": "",
            "reason": err or "blocked",
            "shelf": "none",
            "tokens": 0,
            "claimed_graphrag": False,
            "halted": "kill_switch" in err or "HALT" in err,
        }
    extra: Dict[str, Any] = {}
    summary = result.response_summary or ""
    if summary.startswith("{"):
        try:
            parsed = json.loads(summary)
            if isinstance(parsed, dict):
                extra = parsed
        except json.JSONDecodeError:
            extra = {}
    if extra.get("shelf"):
        shelf = extra["shelf"]
    elif result.dry_run or not extra.get("live"):
        shelf = "none"
    else:
        shelf = "unknown"
    return {
        "ok": bool(result.ok),
        "live": bool(extra.get("live")),
        "text": extra.get("text") or "",
        "reason": extra.get("reason") or err,
        "shelf": shelf,
        "tokens": int(extra.get("tokens") or result.tokens or 0),
        "claimed_graphrag": False,
        "halted": False,
    }


def first_day(system: Any) -> Dict[str, Any]:
    seed = seed_starter_house(system)
    if seed.get("seeded") and house_enabled():
        for doc in STARTER_DOCS:
            _append({"kind": "note", **doc})
    result = system.execute_charter(STARTER_CHARTER)
    receipt = system.issue_stranger_receipt()
    if house_enabled():
        _append({"kind": "receipt", **receipt})
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
    from .house_sign import verify_sig
    from .stranger_receipt import verify_chain, verify_receipt

    p = Path(path)
    if not p.is_file():
        return {"ok": False, "hash_ok": False, "sig": "sig_absent", "reason": "missing"}
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return {"ok": False, "hash_ok": False, "sig": "sig_absent", "reason": "empty"}
    if raw.startswith("["):
        blob = json.loads(raw)
        recs = blob if isinstance(blob, list) else [blob]
    elif raw.startswith("{") and "\n{" not in raw:
        recs = [json.loads(raw)]
    else:
        recs = [json.loads(line) for line in raw.splitlines() if line.strip()]
    recs = [r for r in recs if isinstance(r, dict) and r.get("hash")]
    if not recs:
        return {
            "ok": False,
            "hash_ok": False,
            "sig": "sig_absent",
            "reason": "no_receipt",
            "n": 0,
        }
    hash_ok = verify_chain(recs) if len(recs) > 1 else verify_receipt(recs[0])
    sig = verify_sig(recs[-1]) if recs else "sig_absent"
    return {
        "ok": bool(hash_ok),
        "hash_ok": bool(hash_ok),
        "sig": sig,
        "sig_ok": sig == "sig_ok",
        "sig_absent": sig == "sig_absent",
        "n": len(recs),
    }


def dispatch(cmd: str, arg: str = "") -> Dict[str, Any]:
    from .system import FlowChartCharterSystem

    cmd = (cmd or "").strip().lower()
    system = FlowChartCharterSystem(seed=15)
    if cmd in {"first-day", "first_day"}:
        return first_day(system)
    if cmd == "remember":
        return remember(system, arg)
    if cmd == "ask":
        return ask_world(arg)
    if cmd == "halt":
        system.harness.kill.halt("preview")
        return {"ok": True, "halted": True}
    if cmd == "arm":
        if hasattr(system.harness.kill, "arm"):
            system.harness.kill.arm()
        return {"ok": True, "halted": False}
    if cmd == "status":
        rec = getattr(system, "last_receipt", None) or {}
        return {
            "ok": True,
            "shelves": shelves(system),
            "receipt_hash": rec.get("hash") or "",
            "halted": str(getattr(system.harness.kill.state, "value", "")) == "HALTED",
        }
    return {"ok": False, "reason": "unknown_cmd"}
