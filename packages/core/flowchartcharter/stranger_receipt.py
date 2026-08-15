"""Stranger receipt — hash-chained proof a third party can verify.

Gate 5: external proof. No vendor notary. SHA-256 chain only.
previousReceiptHash is required (IETF draft-marques-asqav-compliance-receipts).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


_META = {"hash", "previousReceiptHash", "sig", "pub", "sig_alg", "kind"}


def _digest(prev: str, payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(f"{prev}\n{blob}".encode("utf-8")).hexdigest()


def issue_receipt(
    system: Any,
    *,
    prev_hash: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    kg = getattr(system, "knowledge", None)
    units = list((getattr(kg, "data", {}) or {}).get("text_units") or [])
    harness = getattr(system, "harness", None)
    sandbox = getattr(harness, "sandbox", None) if harness else None
    payload = {
        "schema": "fcc.stranger_receipt.v1",
        "ts": time.time(),
        "halt": (
            getattr(getattr(harness, "kill", None), "state", None).value
            if harness
            else "unknown"
        ),
        "text_units": len(units),
        "full_rebuild": bool((getattr(kg, "data", {}) or {}).get("full_rebuild")),
        "claimed_graphrag": False,
        "isolation_score": (
            sandbox.isolation_score() if sandbox is not None else 0.0
        ),
        "policy_not_kernel": True,
        "reduce_mode": "extractive",
    }
    if extra:
        payload.update(extra)
    digest = _digest(prev_hash, payload)
    receipt = {
        **payload,
        "previousReceiptHash": prev_hash,
        "hash": digest,
    }
    from .house_sign import sign_hash

    receipt.update(sign_hash(digest))
    return receipt


def verify_receipt(receipt: Dict[str, Any]) -> bool:
    if not isinstance(receipt, dict):
        return False
    if receipt.get("schema") != "fcc.stranger_receipt.v1":
        return False
    if receipt.get("claimed_graphrag") is True:
        return False
    prev = str(receipt.get("previousReceiptHash") or "")
    expected = str(receipt.get("hash") or "")
    body = {k: v for k, v in receipt.items() if k not in _META}
    return expected == _digest(prev, body) and bool(expected)


def verify_chain(receipts: List[Dict[str, Any]]) -> bool:
    prev = ""
    for rec in receipts:
        if not verify_receipt(rec):
            return False
        if str(rec.get("previousReceiptHash") or "") != prev:
            return False
        prev = str(rec.get("hash") or "")
    return True


def persist_receipt(receipt: Dict[str, Any], directory: Optional[Path] = None) -> str:
    from .kill_law import persist_dir, persist_enabled

    if not persist_enabled() and directory is None:
        return ""
    dest_dir = Path(directory) if directory is not None else persist_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "receipts.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, default=str) + "\n")
    return str(path)
