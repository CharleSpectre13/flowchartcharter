"""Halt Law — one process, one stop button.

Optional wrappers are bypasses. ActionUnit.execute consults this module.
Persist is opt-in (FCC_HARNESS_PERSIST=1 or HarnessKernel persist=True).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

_kill: Any = None
_sandbox: Any = None
_persist = False


def persist_enabled() -> bool:
    env = os.environ.get("FCC_HARNESS_PERSIST", "0")
    if env == "1":
        return True
    if env == "0":
        return False
    return _persist


def persist_dir() -> Path:
    raw = (os.environ.get("FCC_HARNESS_DIR") or "").strip()
    path = Path(raw) if raw else Path("/workspace/artifacts/fcc_harness")
    path.mkdir(parents=True, exist_ok=True)
    return path


def bind(kill: Any, sandbox: Any = None, *, persist: bool = False) -> None:
    """Install the process KillSwitch. Last bind wins."""
    global _kill, _sandbox, _persist
    _kill = kill
    if sandbox is not None:
        _sandbox = sandbox
    if persist:
        _persist = True
        restore(kill)
    else:
        _persist = persist_enabled()
        if _persist:
            restore(kill)


def current_kill() -> Any:
    global _kill
    if _kill is None:
        from .harness import KillSwitch

        _kill = KillSwitch()
        if persist_enabled():
            restore(_kill)
    return _kill


def current_sandbox() -> Any:
    return _sandbox


def restore(kill: Any) -> None:
    path = persist_dir() / "halt.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if str(data.get("state") or "") == "HALTED":
        kill.halt(str(data.get("reason") or "restored"))


def write_halt(reason: str) -> None:
    if not persist_enabled():
        return
    path = persist_dir() / "halt.json"
    blob = {
        "state": "HALTED",
        "reason": reason,
        "at": time.time(),
    }
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    fail_path = persist_dir() / "known_failures.jsonl"
    with fail_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": "halt", **blob}) + "\n")


def clear_halt() -> None:
    if not persist_enabled():
        return
    path = persist_dir() / "halt.json"
    try:
        path.unlink()
    except OSError:
        pass


def refuse_side_effect(action_type: str = "") -> Optional[str]:
    """Return a reason string if the side-effect must not run."""
    kill = current_kill()
    if kill is not None and not getattr(kill, "armed", True):
        return "kill_switch_halted"
    sandbox = current_sandbox()
    if sandbox is None:
        return None
    if hasattr(sandbox, "circuit_open") and sandbox.circuit_open():
        return "circuit_breaker_open"
    kind = (action_type or "").strip()
    if kind and kind not in ("llm_live",):
        allow = getattr(getattr(sandbox, "policy", None), "allowlist", None)
        if allow is not None and kind not in allow:
            from .execution_sandbox import ALLOWED_ACTIONS

            if kind not in ALLOWED_ACTIONS:
                return "action_not_allowlisted"
    return None


def apply_sandbox_policy(unit: Any, config: dict) -> None:
    """Playpen wins. Caller cannot unset dry-run via payload."""
    sandbox = current_sandbox()
    if sandbox is None:
        return
    policy = getattr(sandbox, "policy", None)
    if policy is None:
        return
    if bool(getattr(policy, "dry_run", True)) or not bool(
        getattr(policy, "network_allowed", False)
    ):
        config["dry_run"] = True
        if hasattr(unit, "dry_run"):
            unit.dry_run = True
