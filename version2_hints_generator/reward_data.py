from __future__ import annotations

from typing import Any

from models import HintFeedback


def compute_penalty(too_revealing: int) -> float:
    return float(max(1, min(5, too_revealing)))


def compute_hint_score(clarity: int, usefulness: int, relevance: int, too_revealing: int) -> float:
    avg = (clarity + usefulness + relevance) / 3
    return avg - compute_penalty(too_revealing)


def build_scored_hints(feedback_items: list[dict[str, Any]]) -> list[HintFeedback]:
    scored: list[HintFeedback] = []
    for item in feedback_items:
        clarity = int(item["clarity"])
        usefulness = int(item["usefulness"])
        relevance = int(item["relevance"])
        too_revealing = int(item["too_revealing"])
        penalty = compute_penalty(too_revealing)
        score = compute_hint_score(clarity, usefulness, relevance, too_revealing)
        scored.append(
            HintFeedback(
                hint=str(item["hint"]),
                clarity=clarity,
                usefulness=usefulness,
                relevance=relevance,
                too_revealing=too_revealing,
                penalty=penalty,
                score=score,
            )
        )
    return scored


def build_preference_pairs(prompt_json: str, scored_hints: list[HintFeedback]) -> list[dict[str, Any]]:
    if len(scored_hints) < 2:
        return []

    # Requested behavior: for 3 hints, pair every better hint against the weakest hint.
    rejected = min(scored_hints, key=lambda x: x.score)
    pairs: list[dict[str, Any]] = []
    for item in scored_hints:
        if item.hint == rejected.hint:
            continue
        if item.score <= rejected.score:
            continue
        pairs.append(
            {
                "prompt": prompt_json,
                "chosen": item.hint,
                "rejected": rejected.hint,
            }
        )
    return pairs
