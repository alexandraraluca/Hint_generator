from __future__ import annotations

import json
from typing import Any


def _clean_test_value(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"", "?", "null", "None"}:
        return ""
    return text


def build_prompt_payload(
    statement: str,
    student_code: str,
    verdict: str,
    test_data: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "prompt": {
            "statement": statement or "",
            "code": student_code or "",
            "verdict": verdict or "UNKNOWN",
            "test": test_data or {},
        }
    }
    if isinstance(payload["prompt"]["test"], dict):
        payload["prompt"]["test"] = {
            key: _clean_test_value(value) for key, value in payload["prompt"]["test"].items()
        }
    return payload


def build_hint_prompt(
    statement: str,
    student_code: str,
    verdict: str,
    test_data: dict[str, Any] | None,
    n_hints: int = 3,
) -> tuple[str, str]:
    payload = build_prompt_payload(
        statement=statement,
        student_code=student_code,
        verdict=verdict,
        test_data=test_data,
    )
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    prompt = f"""
You are a beginner-friendly programming tutor.

Generate {n_hints} candidate next-step hints for a student.

GOAL:
Help the student discover the core idea of the problem step by step.

STRICT REQUIREMENTS:
- Do NOT provide full solution code or final answer.
- Each hint must be 1-2 sentences.
- Each hint must suggest exactly ONE concrete next step.
- Hints must focus on the underlying algorithmic idea, NOT code debugging.
- Avoid generic advice (e.g., "check your code", "consider edge cases").
- Avoid misleading directions.
- Prefer insights about patterns, invariants, or structure in the problem.
- If failing-test evidence is available, use it to point toward the mistake.

QUALITY GUIDELINES:
- Good hint: leads toward the key insight of the problem.
- Bad hint: focuses on syntax, loops, or vague debugging steps.
- Hints should be diverse and progressively more informative.
- Hints should be relevant to the problem statement and student code.
- Hints should be specific to the problem and not generic.
- Hints should be helpful to the student and not misleading.

Input JSON:
{payload_json}

Return strict JSON:
{{
  "hints": [
        "...",
        "...",
        "..."
  ]
}}

Do not include any text before or after the JSON.
""".strip()
    return prompt, payload_json
