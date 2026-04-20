from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from config import MERGED_PROBLEMS_PATH, SUBMISSIONS_PATH
from models import Problem, Submission, TutorialData


def _normalize_code(tokenized_code: str) -> str:
    lines = tokenized_code.splitlines()
    if not lines:
        return tokenized_code
    return " ".join(line.strip() for line in lines if line.strip()).replace(" ;", ";")


def _looks_like_code(text: str | None) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False

    lowered = raw.lower()
    signal_tokens = [
        "#include",
        "using namespace",
        "int main",
        "public static void main",
        "def ",
        "cin >>",
        "cout <<",
        "scanf(",
        "printf(",
        "return 0",
    ]
    token_hits = sum(1 for token in signal_tokens if token in lowered)
    punct_hits = sum(raw.count(ch) for ch in "{};")
    code_words_hits = len(
        re.findall(r"\b(for|while|if|else|switch|vector|class|struct|void|int|long|bool)\b", lowered)
    )

    return token_hits >= 1 or punct_hits >= 12 or code_words_hits >= 8


def _pick_solution_text(tutorial_raw: dict[str, Any]) -> str | None:
    """
    Pick the best available textual editorial/tutorial.

    Priority:
      1) tutorial.solution if it looks textual
      2) tutorial.Tutorial if textual
      3) tutorial.Editorial if textual
      4) fallback to first non-empty among solution/Tutorial/Editorial
    """
    solution = tutorial_raw.get("solution")
    tutorial_text = tutorial_raw.get("Tutorial")
    editorial_text = tutorial_raw.get("Editorial")

    textual_candidates = [solution, tutorial_text, editorial_text]
    for candidate in textual_candidates:
        candidate_text = str(candidate or "").strip()
        if candidate_text and not _looks_like_code(candidate_text):
            return candidate_text

    for candidate in textual_candidates:
        candidate_text = str(candidate or "").strip()
        if candidate_text:
            return candidate_text

    return None


@lru_cache(maxsize=1)
def load_problems() -> dict[str, Problem]:
    raw: dict[str, Any] = json.loads(MERGED_PROBLEMS_PATH.read_text(encoding="utf-8"))
    problems: dict[str, Problem] = {}
    for problem_id, value in raw.items():
        tutorial_raw = value.get("tutorial") or {}
        tutorial = TutorialData(
            code=tutorial_raw.get("code"),
            hints=tutorial_raw.get("hints"),
            solution=_pick_solution_text(tutorial_raw),
        )
        problems[problem_id] = Problem(
            problem_id=problem_id,
            link=value.get("link"),
            name=value.get("name"),
            statement=value.get("statement"),
            tutorial=tutorial,
        )
    return problems


@lru_cache(maxsize=1)
def load_submissions() -> dict[str, Submission]:
    raw: dict[str, Any] = json.loads(SUBMISSIONS_PATH.read_text(encoding="utf-8"))
    submissions: dict[str, Submission] = {}
    for submission_id, value in raw.items():
        submissions[submission_id] = Submission(
            submission_id=submission_id,
            problem_id=str(value.get("problem_id", "")),
            code=_normalize_code(str(value.get("code", ""))),
            verdict=str(value.get("verdict", "UNKNOWN")),
            test=value.get("test"),
        )
    return submissions


def submissions_for_problem(problem_id: str) -> list[Submission]:
    return [s for s in load_submissions().values() if s.problem_id == problem_id]
