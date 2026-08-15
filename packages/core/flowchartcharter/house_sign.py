"""Optional Ed25519 house signature. Offline. No vendor.

Hash chain stays required. Signature is extra. No keypair → sig_absent.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def sign_enabled() -> bool:
    if os.environ.get("FCC_HARNESS_PERSIST") == "0":
        return False
    return os.environ.get("FCC_HOUSE_SIGN", "1") != "0"


def _key_dir() -> Path:
    raw = (os.environ.get("FCC_HOUSE_PATH") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve().parent
    from .kill_law import persist_dir

    return persist_dir()


def load_or_create_keys() -> Optional[Tuple[Ed25519PrivateKey, bytes]]:
    if not sign_enabled():
        return None
    folder = _key_dir()
    folder.mkdir(parents=True, exist_ok=True)
    priv_path = folder / "house.ed25519"
    if priv_path.is_file():
        raw = priv_path.read_bytes()
        priv = Ed25519PrivateKey.from_private_bytes(raw)
    else:
        priv = Ed25519PrivateKey.generate()
        priv_path.write_bytes(priv.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption(),
        ))
        try:
            priv_path.chmod(0o600)
        except OSError:
            pass
    pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return priv, pub


def sign_hash(digest: str) -> Dict[str, str]:
    pair = load_or_create_keys()
    if pair is None:
        return {}
    priv, pub = pair
    sig = priv.sign(digest.encode("utf-8"))
    return {
        "sig_alg": "ed25519",
        "sig": base64.b64encode(sig).decode("ascii"),
        "pub": base64.b64encode(pub).decode("ascii"),
    }


def verify_sig(receipt: Dict[str, Any]) -> str:
    """Return sig_ok | sig_bad | sig_absent."""
    sig_b = receipt.get("sig")
    pub_b = receipt.get("pub")
    digest = str(receipt.get("hash") or "")
    if not sig_b or not pub_b or not digest:
        return "sig_absent"
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(str(pub_b)))
        pub.verify(base64.b64decode(str(sig_b)), digest.encode("utf-8"))
        return "sig_ok"
    except Exception:  # noqa: BLE001
        return "sig_bad"
