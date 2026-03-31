from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TutorialData:
    code: str | None
    hints: list[str] | None
    solution: str | None


@dataclass
class Problem:
    problem_id: str
    link: str | None
    name: str | None
    statement: str | None
    tutorial: TutorialData


@dataclass
class Submission:
    submission_id: str
    problem_id: str
    code: str
    verdict: str
    test: dict[str, Any] | None


@dataclass
class HintFeedback:
    hint: str
    clarity: int
    usefulness: int
    relevance: int
    too_revealing: int
    penalty: float
    score: float
