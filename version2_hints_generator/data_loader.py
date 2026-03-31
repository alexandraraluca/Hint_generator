from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from config import MERGED_PROBLEMS_PATH, SUBMISSIONS_PATH
from models import Problem, Submission, TutorialData


def _normalize_code(tokenized_code: str) -> str:
    lines = tokenized_code.splitlines()
    if not lines:
        return tokenized_code
    return " ".join(line.strip() for line in lines if line.strip()).replace(" ;", ";")


@lru_cache(maxsize=1)
def load_problems() -> dict[str, Problem]:
    raw: dict[str, Any] = json.loads(MERGED_PROBLEMS_PATH.read_text(encoding="utf-8"))
    problems: dict[str, Problem] = {}
    for problem_id, value in raw.items():
        tutorial_raw = value.get("tutorial") or {}
        tutorial = TutorialData(
            code=tutorial_raw.get("code"),
            hints=tutorial_raw.get("hints"),
            solution=tutorial_raw.get("solution"),
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
