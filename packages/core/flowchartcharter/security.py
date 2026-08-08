"""Admin API-key security for /system/* management endpoints.

Workload ingestion may remain open. System management (Monday Sync,
playbook load, analytics force, personnel upgrade) requires:

  Header: X-API-Key: <FCC_ADMIN_KEY>

Env:
  FCC_ADMIN_KEY     — required secret for admin routes
  FCC_ADMIN_OPEN=1  — explicit open mode for local demos/tests only
"""

from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def admin_key_configured() -> Optional[str]:
    return os.environ.get("FCC_ADMIN_KEY") or None


def admin_open_mode() -> bool:
    return os.environ.get("FCC_ADMIN_OPEN", "0") == "1"


def ensure_admin_key_on_boot() -> dict:
    """Boot policy: production must set key; open mode is explicit."""
    key = admin_key_configured()
    if key:
        return {"mode": "locked", "key_set": True, "key_fingerprint": key[:4] + "…"}
    if admin_open_mode():
        return {"mode": "open", "key_set": False, "warning": "FCC_ADMIN_OPEN=1"}
    # Generate ephemeral key so production isn't wide open by accident
    generated = secrets.token_urlsafe(24)
    os.environ["FCC_ADMIN_KEY"] = generated
    return {
        "mode": "locked_ephemeral",
        "key_set": True,
        "generated": True,
        "key": generated,  # surfaced once at boot logs only
        "warning": "FCC_ADMIN_KEY was unset — generated ephemeral key for this process",
    }


async def require_admin_key(
    api_key: Optional[str] = Security(API_KEY_HEADER),
) -> str:
    """FastAPI dependency — gate all /system/* management routes."""
    if admin_open_mode() and not admin_key_configured():
        return "open"

    expected = admin_key_configured()
    if not expected:
        # Should not happen after ensure_admin_key_on_boot, but fail closed
        raise HTTPException(
            status_code=503,
            detail="Admin key not configured. Set FCC_ADMIN_KEY.",
        )
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-Key for system management endpoint",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
