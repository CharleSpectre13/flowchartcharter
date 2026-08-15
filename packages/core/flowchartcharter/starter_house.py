"""First-day house — not a blank attic.

Public notebook so a person can work before they feed anything.
This is not GraphRAG. This is not a new Grok. It is the welcome mat.
"""

from __future__ import annotations

from typing import Dict, List

STARTER_CHARTER = "First Day — finish one small job, then stop"

STARTER_DOCS: List[Dict[str, str]] = [
    {
        "source_id": "house-welcome",
        "text": (
            "FlowChartCharter is an open cookbook. The Charter is the map. "
            "The harness is the car. Halt is the stop button. "
            "You do not need a paid key to start."
        ),
    },
    {
        "source_id": "house-shelves",
        "text": (
            "Two shelves. The world mouth is Grok or a house chef you chose. "
            "The house notebook is your jobs and receipts. "
            "The notebook starts small. The mouth is optional."
        ),
    },
    {
        "source_id": "house-halt",
        "text": (
            "If something goes wrong press Halt. New side effects freeze. "
            "Done is not a wink. A checker signs the receipt."
        ),
    },
]


def starter_seeded(kg: object) -> bool:
    data = getattr(kg, "data", {}) or {}
    units = data.get("text_units") or []
    return any(
        isinstance(u, dict) and str(u.get("source_id") or "").startswith("house-")
        for u in units
    )
