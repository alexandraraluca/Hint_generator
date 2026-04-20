from __future__ import annotations

from models import Concept
from llm_client import ollama_chat, parse_json_response
from prompting import build_concept_extraction_prompt


def extract_concepts(statement: str, solution: str) -> list[Concept]:
    """
    Call the LLM to extract key concepts from a problem + editorial solution.
    Returns a list of Concept objects (3-5 typically).
    Raises RuntimeError if the LLM call fails.
    """
    prompt = build_concept_extraction_prompt(statement, solution)
    raw = ollama_chat(
        user_prompt=prompt,
        system_prompt=(
            "Return only valid JSON. "
            "Schema: {\"concepts\":[{\"id\":\"c1\",\"name\":\"...\","
            "\"description\":\"...\",\"prerequisites\":[]}]}."
        ),
        temperature=0.3,
    )
    data = parse_json_response(raw)
    concepts_raw = data.get("concepts", [])

    concepts: list[Concept] = []
    seen_ids: set[str] = set()

    for item in concepts_raw:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        prereqs = item.get("prerequisites", [])
        if not isinstance(prereqs, list):
            prereqs = []
        prereqs = [str(p).strip() for p in prereqs if p]

        if cid and name and cid not in seen_ids:
            concepts.append(
                Concept(id=cid, name=name, description=description, prerequisites=prereqs)
            )
            seen_ids.add(cid)

    return concepts


def topological_sort(concepts: list[Concept]) -> list[str]:
    """
    Return concept IDs ordered so that every prerequisite appears
    before the concepts that depend on it (Kahn's algorithm).
    Falls back to original order if a cycle is detected.
    """
    valid_ids = {c.id for c in concepts}
    in_degree: dict[str, int] = {c.id: 0 for c in concepts}
    children: dict[str, list[str]] = {c.id: [] for c in concepts}

    for c in concepts:
        for prereq in c.prerequisites:
            if prereq in valid_ids:
                in_degree[c.id] += 1
                children[prereq].append(c.id)

    queue = [cid for cid, deg in in_degree.items() if deg == 0]
    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for child in children[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    # Cycle detected — fall back to original insertion order
    if len(result) < len(concepts):
        return [c.id for c in concepts]

    return result


def get_concept_by_id(concepts: list[Concept], cid: str) -> Concept | None:
    for c in concepts:
        if c.id == cid:
            return c
    return None
