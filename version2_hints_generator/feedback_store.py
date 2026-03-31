from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from config import FEEDBACK_LOG_PATH, PREFERENCE_PAIRS_PATH


def append_feedback(entry: dict[str, Any]) -> None:
    payload = {**entry, "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    with FEEDBACK_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def append_preference_pairs(entries: list[dict[str, Any]]) -> None:
    if not entries:
        return
    with PREFERENCE_PAIRS_PATH.open("a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_feedback_count() -> int:
    if not FEEDBACK_LOG_PATH.exists():
        return 0
    with FEEDBACK_LOG_PATH.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def load_pairs_count() -> int:
    if not PREFERENCE_PAIRS_PATH.exists():
        return 0
    with PREFERENCE_PAIRS_PATH.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)
