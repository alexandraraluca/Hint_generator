from __future__ import annotations

from dataclasses import dataclass, field
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
class Concept:
    id: str
    name: str
    description: str
    prerequisites: list[str] = field(default_factory=list)


@dataclass
class HintFeedback:
    hint: str
    rating: str  # "ok" or "not_ok"

    @property
    def score(self) -> float:
        return 1.0 if self.rating == "ok" else 0.0
