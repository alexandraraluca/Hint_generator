from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from config import DEFAULT_MODEL, DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
    return {"hints": []}


def _extract_hints(payload: Any, expected_count: int) -> list[str]:
    if not isinstance(payload, dict):
        return []
    raw_hints = payload.get("hints", [])
    if not isinstance(raw_hints, list):
        return []

    hints: list[str] = []
    for item in raw_hints:
        text = ""
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
        elif isinstance(item, str):
            text = item.strip()
        if text:
            hints.append(text)
    return hints[:expected_count]


def _generate_with_ollama(prompt: str, temperature: float) -> list[str]:
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    url = f"{base_url}/api/generate"
    request_payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": temperature},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode("utf-8")
    outer = json.loads(raw)
    model_text = str(outer.get("response", "")).strip()
    return _extract_hints(_extract_json(model_text), expected_count=3)


def _generate_with_openai(prompt: str, model: str, temperature: float) -> list[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": "You produce concise tutoring hints."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or ""
    return _extract_hints(_extract_json(content), expected_count=3)


def _fallback_hints(verdict: str) -> list[str]:
    verdict_up = verdict.upper()
    if "WRONG_ANSWER" in verdict_up:
        return [
            "Porneste de la primul caz in care raspunsul difera si descrie ce tranzitie ar trebui sa se aplice in acea stare.",
            "Defineste clar starea DP si verifica daca fiecare tranzitie foloseste doar subprobleme deja calculate.",
            "Verifica baza DP pentru dimensiuni minime, apoi urmareste cum se propaga rezultatul catre starea finala.",
        ]
    if "TIME_LIMIT" in verdict_up:
        return [
            "Exprima solutia ca recurenta DP si identifica ce dimensiuni fac varianta curenta prea lenta.",
            "Cauta o optimizare de tranzitii prin prefixe/sufixe sau memorare de valori agregate.",
            "Verifica daca poti reduce numarul de stari sau dependentele dintre ele fara sa schimbi corectitudinea.",
        ]
    return [
        "Inainte de implementare, scrie in cuvinte ce inseamna o stare DP valida pentru aceasta problema.",
        "Construieste relatia de tranzitie pentru o stare si verifica pe un exemplu mic daca acopera toate cazurile.",
        "Stabileste ordinea de calcul a starilor astfel incat fiecare stare sa foloseasca doar rezultate deja disponibile.",
    ]


def generate_candidate_hints(
    prompt: str,
    verdict: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.5,
) -> list[str]:
    try:
        hints = _generate_with_ollama(prompt, temperature=temperature)
        if hints:
            return hints
    except Exception:
        pass
    try:
        hints = _generate_with_openai(prompt, model=model, temperature=temperature)
        if hints:
            return hints
    except Exception:
        pass
    return _fallback_hints(verdict)
