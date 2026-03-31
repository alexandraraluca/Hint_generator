from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from config import (
    CLASSIFICATION_DATASET_PATH,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    MERGED_PROBLEMS_PATH,
    SUBMISSIONS_PATH,
)

ALLOWED_ERROR_TYPES = {
    "logic",
    "edge case",
    "complexity",
    "implementation bug",
    "misunderstanding problem",
    "correct",
}


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]..."


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"?", "null", "None"}:
        return ""
    return text


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
    return {}


def _normalize_error_type(raw_error_type: str, verdict: str) -> str:
    verdict_up = verdict.upper()
    if "ACCEPTED" in verdict_up:
        return "correct"

    candidate = " ".join(raw_error_type.lower().split())
    if candidate in ALLOWED_ERROR_TYPES:
        return candidate

    mapping = {
        "edge_case": "edge case",
        "edge-case": "edge case",
        "implementation_bug": "implementation bug",
        "misunderstanding": "misunderstanding problem",
        "misunderstanding the problem": "misunderstanding problem",
    }
    return mapping.get(candidate, "logic")


def _extract_problem_hint(problem_entry: dict[str, Any]) -> str:
    tutorial = problem_entry.get("tutorial") if isinstance(problem_entry, dict) else None
    hints = tutorial.get("hints") if isinstance(tutorial, dict) else None
    if isinstance(hints, list):
        non_empty = [_clean_text(h) for h in hints if _clean_text(h)]
        if non_empty:
            return non_empty[0]
    if isinstance(hints, str):
        hint_text = _clean_text(hints)
        if hint_text:
            return hint_text
    return "No hint loaded"


def _hint_for_problem_id(problems_raw: dict[str, Any], problem_id: str) -> str:
    # Hint source is strictly code_solution_hints_merged.json matched by problem_id.
    problem_entry = problems_raw.get(problem_id)
    if not isinstance(problem_entry, dict):
        return "No hint loaded"
    return _extract_problem_hint(problem_entry)


def _prompt_for_submission(
    statement: str,
    code: str,
    verdict: str,
    test_data: dict[str, Any] | None,
) -> str:
    clipped_statement = _clip(statement, 3500)
    clipped_code = _clip(code, 3500)
    clipped_test = test_data if isinstance(test_data, dict) else {}
    clipped_test = {
        key: _clip(_clean_text(value), 1200) for key, value in clipped_test.items()
    }

    payload = {
        "statement": clipped_statement,
        "code": clipped_code,
        "verdict": verdict,
        "test": clipped_test,
    }
    return f"""
You are a programming tutor specialized in bug categorization.

Classify the submission into exactly one error category:
- logic
- edge case
- complexity
- implementation bug
- misunderstanding problem
- correct (use this only if verdict is Accepted)

Rules:
- If verdict indicates Accepted, output error_type = "correct".
- Use verdict + failing test details as strong evidence when available.
- Return only strict JSON with this schema:
{{
  "error_type": "..."
}}

Submission payload:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


def _call_ollama(prompt: str, retries: int = 2) -> dict[str, Any]:
    url = f"{DEFAULT_OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    request_payload = {
        "model": DEFAULT_OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(request_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                outer = json.loads(resp.read().decode("utf-8"))
            parsed = _extract_json(str(outer.get("response", "")).strip())
            if parsed:
                return parsed
        except Exception:
            if attempt == retries:
                break
            time.sleep(1.0 * attempt)
    return {}


def _fallback_error_type(verdict: str) -> str:
    verdict_up = verdict.upper()
    if "ACCEPTED" in verdict_up:
        return "correct"
    if "TIME_LIMIT" in verdict_up:
        return "complexity"
    if "RUNTIME" in verdict_up:
        return "implementation bug"
    return "logic"


def _save_dataset(path: Path, dataset: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Process at most N new submissions.")
    args = parser.parse_args()

    submissions_raw = _read_json(SUBMISSIONS_PATH)
    problems_raw = _read_json(MERGED_PROBLEMS_PATH)

    # Fresh-run only mode: always rebuild dataset from scratch.
    dataset: list[dict[str, Any]] = []
    _save_dataset(CLASSIFICATION_DATASET_PATH, dataset)

    total = len(submissions_raw)
    processed_now = 0

    for idx, (submission_id, sub) in enumerate(submissions_raw.items(), start=1):
        if args.limit and processed_now >= args.limit:
            break

        problem_id = str(sub.get("problem_id", ""))
        statement = _clean_text((problems_raw.get(problem_id) or {}).get("statement", ""))
        code = _clean_text(sub.get("code", ""))
        verdict = _clean_text(sub.get("verdict", "UNKNOWN"))
        test_data = sub.get("test")

        prompt = _prompt_for_submission(
            statement=statement,
            code=code,
            verdict=verdict,
            test_data=test_data if isinstance(test_data, dict) else None,
        )
        model_out = _call_ollama(prompt)
        raw_error_type = _clean_text(model_out.get("error_type", ""))
        if raw_error_type:
            error_type = _normalize_error_type(raw_error_type, verdict=verdict)
        else:
            error_type = _fallback_error_type(verdict)
        hint = _hint_for_problem_id(problems_raw, problem_id)

        row = {
            "submission_id": submission_id,
            "statement": statement,
            "code": code,
            "verdict": verdict,
            "error_type": error_type,
            "hint": hint,
        }
        dataset.append(row)
        processed_now += 1

        # Save after each submission to guarantee persistence before moving on.
        _save_dataset(CLASSIFICATION_DATASET_PATH, dataset)
        print(f"[{idx}/{total}] saved submission_id={submission_id} error_type={error_type}")

    print(f"Done. Fresh run completed. Processed: {processed_now} | Total rows: {len(dataset)}")


if __name__ == "__main__":
    main()
