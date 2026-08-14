"""v2.2.0 Secret Scrubber + StatePersister Vault (R1).

Write-time redaction so system_state.json never stores tokens, webhooks,
or provider secrets. Complements action_units.redact_secrets for telemetry.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

# Keys (substring match, case-insensitive)
SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "webhook",
    "api_key",
    "apikey",
    "password",
    "secret",
    "authorization",
    "auth",
    "bearer",
    "private_key",
    "access_token",
    "client_secret",
    "fcc_github",
    "fcc_slack",
    "fcc_admin",
)

# Value patterns (GitHub PAT, Slack bot, Bearer, Slack webhook URL)
SENSITIVE_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+"),
]

REDACTED_KEY = "REDACTED_BY_FCC_VAULT"
REDACTED_PATTERN = "REDACTED_SECRET_PATTERN"


class SecretScrubber:
    """Recursively scrub sensitive keys and regex patterns from snapshots."""

    SENSITIVE_KEYS = set(SENSITIVE_KEY_FRAGMENTS)
    SENSITIVE_PATTERNS = SENSITIVE_PATTERNS

    @classmethod
    def scrub(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            out: Dict[str, Any] = {}
            for k, v in data.items():
                key_l = str(k).lower()
                if any(sk in key_l for sk in cls.SENSITIVE_KEYS):
                    out[str(k)] = REDACTED_KEY
                else:
                    out[str(k)] = cls.scrub(v)
            return out
        if isinstance(data, list):
            return [cls.scrub(item) for item in data]
        if isinstance(data, tuple):
            return tuple(cls.scrub(item) for item in data)
        if isinstance(data, str):
            val = data
            for pattern in cls.SENSITIVE_PATTERNS:
                val = pattern.sub(REDACTED_PATTERN, val)
            return val
        return data

    @classmethod
    def is_clean(cls, data: Any) -> bool:
        """True if no raw secret patterns remain after scrub (or in raw)."""
        blob = json.dumps(cls.scrub(data) if not isinstance(data, str) else data)
        for pattern in cls.SENSITIVE_PATTERNS:
            if pattern.search(blob) and REDACTED_PATTERN not in blob:
                # pattern matched non-redacted content
                raw = json.dumps(data, default=str)
                if pattern.search(raw):
                    return False
        raw = json.dumps(data, default=str)
        for pattern in cls.SENSITIVE_PATTERNS:
            if pattern.search(raw):
                # still present only if scrub missed — check scrubbed
                scrubbed = json.dumps(cls.scrub(data), default=str)
                if pattern.search(scrubbed):
                    return False
        return True


class StatePersisterVault:
    """Optional vault wrapper: scrub then write JSON snapshot."""

    def __init__(self, filepath: str = "system_state.json") -> None:
        self.filepath = filepath
        self.scrub_count = 0

    def snapshot(self, state_dict: dict) -> str:
        safe_data = SecretScrubber.scrub(state_dict)
        self.scrub_count += 1
        path = Path(self.filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(safe_data, indent=2, default=str),
            encoding="utf-8",
        )
        return str(path)

    def load(self) -> Optional[Dict[str, Any]]:
        path = Path(self.filepath)
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None


def scrub_payload(data: Any) -> Any:
    """Module-level alias used by StatePersister.save."""
    return SecretScrubber.scrub(data)
