from __future__ import annotations

from typing import Any

from models import HintFeedback


def build_feedback_items(hints: list[str], ratings: dict[int, str]) -> list[HintFeedback]:
    """
    Convert parallel hint list + ratings dict into HintFeedback objects.
    ratings keys are 0-based indices; values are "ok" or "not_ok".
    """
    return [
        HintFeedback(hint=hint, rating=ratings.get(i, "not_ok"))
        for i, hint in enumerate(hints)
        if hint.strip()
    ]


def build_preference_pairs(
    prompt_json: str,
    feedback_items: list[HintFeedback],
) -> list[dict[str, Any]]:
    """
    Build DPO-style preference pairs from binary ok/not_ok feedback.

    Every "ok" hint is paired against every "not_ok" hint as (chosen, rejected).
    These pairs are the training signal for a reward model or direct preference
    optimisation fine-tune.
    """
    ok_hints = [f for f in feedback_items if f.rating == "ok"]
    not_ok_hints = [f for f in feedback_items if f.rating == "not_ok"]

    pairs: list[dict[str, Any]] = []
    for chosen in ok_hints:
        for rejected in not_ok_hints:
            pairs.append(
                {
                    "prompt": prompt_json,
                    "chosen": chosen.hint,
                    "rejected": rejected.hint,
                }
            )
    return pairs
