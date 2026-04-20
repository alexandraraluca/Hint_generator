from __future__ import annotations

import json
from typing import Any

from models import Concept


def build_concept_extraction_prompt(statement: str, solution: str) -> str:
    return f"""You are an expert competitive programming tutor.

Analyze this problem and its editorial solution. Extract 3-5 key concepts a student must understand to solve it.
Build a dependency graph where each concept may require understanding other concepts first (prerequisites).

Problem statement:
{statement[:3000]}

Official solution approach:
{solution[:2000]}

Return JSON. Use simple IDs like c1, c2, c3:
{{
  "concepts": [
    {{"id": "c1", "name": "...", "description": "One sentence specific to this problem.", "prerequisites": []}},
    {{"id": "c2", "name": "...", "description": "...", "prerequisites": ["c1"]}},
    {{"id": "c3", "name": "...", "description": "...", "prerequisites": ["c1", "c2"]}}
  ]
}}

Rules:
- 3 to 5 concepts only
- Order from most fundamental to most specific/complex
- Prerequisites must be IDs of other concepts in the same list
- Descriptions must be specific to THIS problem, not generic definitions
- The last concept should represent the core insight of the solution
""".strip()


def build_code_analysis_prompt(
    statement: str,
    solution_text: str,
    solution_code: str | None,
    student_code: str,
    test_data: dict[str, Any] | None,
    verdict: str,
    concepts: list[Concept],
) -> str:
    concept_list = "\n".join(
        f"  {c.id}: {c.name} — {c.description}" for c in concepts
    )
    test_block = ""
    if test_data:
        test_block = f"""
Failed test:
  Input: {str(test_data.get('input', 'N/A'))[:300]}
  Expected output: {str(test_data.get('jury_answer', 'N/A'))[:200]}
  Student output: {str(test_data.get('participant_output', 'N/A'))[:200]}
  Checker comment: {str(test_data.get('checker_comment', 'N/A'))[:200]}
"""
    sol_code_block = f"\nOfficial solution code:\n{solution_code[:1500]}" if solution_code else ""

    return f"""You are an expert competitive programming tutor analyzing a student's wrong submission.

Problem statement:
{statement[:2000]}

Official solution approach:
{solution_text[:1500]}
{sol_code_block}

Student's code:
{student_code[:1500]}

Verdict: {verdict}
{test_block}
Key concepts needed (ordered from fundamental to advanced):
{concept_list}

Identify which concept the student is most likely missing or implementing incorrectly.
Look at the failed test evidence to pinpoint the issue precisely.

Return JSON:
{{
  "missing_concept_id": "c1",
  "reason": "One clear sentence explaining what the student is doing wrong and why."
}}
""".strip()


def build_general_hint_prompt(
    statement: str,
    solution: str,
    concept: Concept,
) -> tuple[str, str]:
    payload = {
        "problem_statement": statement[:2000],
        "solution_approach": solution[:1500],
        "target_concept": {
            "name": concept.name,
            "description": concept.description,
        },
    }
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    prompt = f"""You are a beginner-friendly competitive programming tutor.

The student does not understand this concept:
  "{concept.name}" — {concept.description}

Generate exactly 2 diverse hints to guide the student toward understanding this concept in the context of the problem.

STRICT RULES:
- Do NOT give the solution or solution code
- Each hint must be 1-2 sentences only
- Both hints must be specific to this problem, not generic advice
- Hint 1: point toward the key insight or observation needed
- Hint 2: suggest a concrete next step or small experiment to try
- Be encouraging, not condescending

Input context:
{payload_json}

Return JSON:
{{"hints": ["hint 1 text", "hint 2 text"]}}
""".strip()
    return prompt, payload_json


def build_specific_hint_prompt(
    statement: str,
    solution_text: str,
    solution_code: str | None,
    student_code: str,
    test_data: dict[str, Any] | None,
    verdict: str,
    concept: Concept,
    analysis_reason: str,
) -> tuple[str, str]:
    test_block = {}
    if test_data:
        test_block = {
            "input": str(test_data.get("input", ""))[:300],
            "expected": str(test_data.get("jury_answer", ""))[:200],
            "student_output": str(test_data.get("participant_output", ""))[:200],
            "checker": str(test_data.get("checker_comment", ""))[:200],
        }

    payload = {
        "problem_statement": statement[:1500],
        "solution_approach": solution_text[:1000],
        "student_code": student_code[:1500],
        "verdict": verdict,
        "failed_test": test_block,
        "missing_concept": {
            "name": concept.name,
            "description": concept.description,
        },
        "diagnosis": analysis_reason,
    }
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    prompt = f"""You are a competitive programming tutor analyzing a specific wrong submission.

The student's mistake is related to: "{concept.name}" — {concept.description}
Diagnosis: {analysis_reason}

Generate exactly 2 targeted hints to help the student understand and fix their specific mistake.

STRICT RULES:
- Do NOT show corrected code or the full solution
- Each hint must be 1-2 sentences
- Hint 1: explain conceptually WHERE the logic breaks down
- Hint 2: hint at WHY the current approach fails on the specific test case
- Be specific to the actual code and test, not generic
- Be encouraging

Input context:
{payload_json}

Return JSON:
{{"hints": ["hint 1 text", "hint 2 text"]}}
""".strip()
    return prompt, payload_json
