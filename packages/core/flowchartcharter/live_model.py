"""Loadable live model Port.

Uses grok-4.5 via XAI_API_KEY when present (xai-api skill).
No key → mock, live=false. Never invents a billed call.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from .llm_bridge import (
    LLMBridge,
    LLMBridgeConfig,
    SamplingParams,
    detect_live_provider,
)


class LiveModel:
    """One object operators `from flowchartcharter import LiveModel`."""

    def __init__(self, bridge: Optional[LLMBridge] = None) -> None:
        self.bridge = bridge or LLMBridge()

    @classmethod
    def from_env(cls) -> "LiveModel":
        return cls(LLMBridge(LLMBridgeConfig.from_env()))

    def status(self) -> Dict[str, Any]:
        cfg = self.bridge.config
        live = bool(self.bridge.live)
        return {
            "live": live,
            "provider": cfg.provider,
            "model": cfg.model if live else "mock-local",
            "key_present": bool(cfg.api_key),
            "key_env": cfg.key_env or "",
            "reduce_mode": "llm" if live else "extractive",
            "detected": detect_live_provider(),
        }

    def complete(self, prompt: str, *, max_tokens: int = 256) -> Dict[str, Any]:
        """Capped completion. Mock if not live. Does not loop."""
        cap = max(32, min(int(max_tokens), 512))
        if not self.bridge.live:
            return {
                "ok": True,
                "live": False,
                "text": "",
                "reason": "port_not_live_mock_contract",
                "tokens": 0,
            }
        result = self.bridge.chat(
            "You are the FlowChartCharter live model. Be brief. No secrets.",
            prompt[:4000],
            sampling=SamplingParams(max_tokens=cap, temperature=0.2),
        )
        return {
            "ok": True,
            "live": True,
            "text": result.text,
            "tokens": result.usage.billed,
            "model": self.bridge.config.model,
        }

    def extract_triples(self, text: str, *, source_id: str = "") -> Dict[str, Any]:
        """Live extract if key + FCC_LIVE_EXTRACT=1. Else heuristic."""
        from .charter_memory import extract_triples

        want = os.environ.get("FCC_LIVE_EXTRACT", "0") == "1"
        if not (want and self.bridge.live):
            prop = extract_triples(text, source_id=source_id)
            return {"mode": "heuristic", "live": False, **prop.to_dict()}
        prompt = (
            "Extract JSON {entities:[{id,title}], relations:[{src,dst,type}]} "
            f"from:\n{text[:2000]}"
        )
        out = self.complete(prompt, max_tokens=300)
        try:
            blob = json.loads(out.get("text") or "{}")
        except json.JSONDecodeError:
            prop = extract_triples(text, source_id=source_id)
            return {"mode": "heuristic_fallback", "live": True, **prop.to_dict()}
        return {"mode": "llm", "live": True, **blob}
