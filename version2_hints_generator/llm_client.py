# from __future__ import annotations

# import json
# import os
# import urllib.request
# from typing import Any

# from config import DEFAULT_MODEL, DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL


# def _extract_json(text: str) -> dict[str, Any]:
#     try:
#         return json.loads(text)
#     except json.JSONDecodeError:
#         start = text.find("{")
#         end = text.rfind("}")
#         if start != -1 and end != -1 and end > start:
#             return json.loads(text[start : end + 1])
#     return {"hints": []}


# def _extract_hints(payload: Any, expected_count: int) -> list[str]:
#     if not isinstance(payload, dict):
#         return []
#     raw_hints = payload.get("hints", [])
#     if not isinstance(raw_hints, list):
#         return []

#     hints: list[str] = []
#     for item in raw_hints:
#         text = ""
#         if isinstance(item, dict):
#             text = str(item.get("text", "")).strip()
#         elif isinstance(item, str):
#             text = item.strip()
#         if text:
#             hints.append(text)
#     return hints[:expected_count]


# def _generate_with_ollama(prompt: str, temperature: float) -> list[str]:
#     base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
#     model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
#     url = f"{base_url}/api/generate"
#     request_payload = {
#         "model": model,
#         "prompt": prompt,
#         "stream": False,
#         "format": "json",
#         "options": {"temperature": temperature},
#     }
#     req = urllib.request.Request(
#         url,
#         data=json.dumps(request_payload).encode("utf-8"),
#         headers={"Content-Type": "application/json"},
#         method="POST",
#     )
#     with urllib.request.urlopen(req, timeout=180) as resp:
#         raw = resp.read().decode("utf-8")
#     outer = json.loads(raw)
#     model_text = str(outer.get("response", "")).strip()
#     return _extract_hints(_extract_json(model_text), expected_count=3)


# def _generate_with_openai(prompt: str, model: str, temperature: float) -> list[str]:
#     api_key = os.getenv("OPENAI_API_KEY")
#     if not api_key:
#         return []
#     from openai import OpenAI

#     client = OpenAI(api_key=api_key)
#     response = client.chat.completions.create(
#         model=model,
#         temperature=temperature,
#         messages=[
#             {"role": "system", "content": "You produce concise tutoring hints."},
#             {"role": "user", "content": prompt},
#         ],
#     )
#     content = response.choices[0].message.content or ""
#     return _extract_hints(_extract_json(content), expected_count=3)


# def _fallback_hints(verdict: str) -> list[str]:
#     verdict_up = verdict.upper()
#     if "WRONG_ANSWER" in verdict_up:
#         return [
#             "Porneste de la primul caz in care raspunsul difera si descrie ce tranzitie ar trebui sa se aplice in acea stare.",
#             "Defineste clar starea DP si verifica daca fiecare tranzitie foloseste doar subprobleme deja calculate.",
#             "Verifica baza DP pentru dimensiuni minime, apoi urmareste cum se propaga rezultatul catre starea finala.",
#         ]
#     if "TIME_LIMIT" in verdict_up:
#         return [
#             "Exprima solutia ca recurenta DP si identifica ce dimensiuni fac varianta curenta prea lenta.",
#             "Cauta o optimizare de tranzitii prin prefixe/sufixe sau memorare de valori agregate.",
#             "Verifica daca poti reduce numarul de stari sau dependentele dintre ele fara sa schimbi corectitudinea.",
#         ]
#     return [
#         "Inainte de implementare, scrie in cuvinte ce inseamna o stare DP valida pentru aceasta problema.",
#         "Construieste relatia de tranzitie pentru o stare si verifica pe un exemplu mic daca acopera toate cazurile.",
#         "Stabileste ordinea de calcul a starilor astfel incat fiecare stare sa foloseasca doar rezultate deja disponibile.",
#     ]


# def generate_candidate_hints(
#     prompt: str,
#     verdict: str,
#     model: str = DEFAULT_MODEL,
#     temperature: float = 0.5,
# ) -> list[str]:
#     try:
#         hints = _generate_with_ollama(prompt, temperature=temperature)
#         if hints:
#             return hints
#     except Exception:
#         pass
#     try:
#         hints = _generate_with_openai(prompt, model=model, temperature=temperature)
#         if hints:
#             return hints
#     except Exception:
#         pass
#     return _fallback_hints(verdict)


from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from config import DEFAULT_MODEL, DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, N_HINTS

LOGGER = logging.getLogger("hint_generator")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    LOGGER.addHandler(handler)

# Debug ON permanently (fara env var)
LOGGER.setLevel(logging.DEBUG)

_LAST_GENERATION_DEBUG: dict[str, Any] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_last_generation_debug(data: dict[str, Any]) -> None:
    global _LAST_GENERATION_DEBUG
    _LAST_GENERATION_DEBUG = {"timestamp_utc": _now_iso(), **data}


def get_last_generation_debug() -> dict[str, Any]:
    return dict(_LAST_GENERATION_DEBUG)


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        return {"hints": []}

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        LOGGER.warning("JSON decode failed: %s", exc)
        LOGGER.debug("Raw model text preview: %s", cleaned[:800])

    for fence in ("```json", "```"):
        if fence in cleaned:
            start = cleaned.find(fence) + len(fence)
            end = cleaned.rfind("```")
            if end > start:
                candidate = cleaned[start:end].strip()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as exc2:
                    LOGGER.warning("JSON fence decode failed: %s", exc2)
                    LOGGER.debug("Fence candidate preview: %s", candidate[:800])

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc3:
            LOGGER.warning("JSON recovery decode failed: %s", exc3)
            LOGGER.debug("Recovery candidate preview: %s", candidate[:800])

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


def _extract_hints_from_text(text: str, expected_count: int) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates: list[str] = []

    numbered_pattern = re.compile(r"^(?:hint\s*\d+[:\-]?|\d+[\.)]\s*)", re.IGNORECASE)
    for line in lines:
        normalized = numbered_pattern.sub("", line).strip("- ")
        if len(normalized) >= 20:
            candidates.append(normalized)
        if len(candidates) >= expected_count:
            return candidates[:expected_count]

    chunks = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", text) if chunk.strip()]
    for chunk in chunks:
        if len(chunk) < 20:
            continue
        if chunk not in candidates:
            candidates.append(chunk)
        if len(candidates) >= expected_count:
            break

    return candidates[:expected_count]


def _coerce_hints(model_text: str, expected_count: int) -> tuple[list[str], str]:
    parsed_payload = _extract_json(model_text)
    hints = _extract_hints(parsed_payload, expected_count=expected_count)
    if hints:
        return hints, "json"

    text_hints = _extract_hints_from_text(model_text, expected_count=expected_count)
    if text_hints:
        return text_hints, "text_fallback"

    return [], "none"


def _generate_with_ollama(prompt: str, temperature: float) -> tuple[list[str], dict[str, Any]]:
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    url = f"{base_url}/api/chat"

    request_payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return only valid JSON. No explanations. "
                    "Schema: {\"hints\":[\"hint 1\",\"hint 2\",\"hint 3\"]}."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": temperature},
    }

    meta: dict[str, Any] = {
        "provider": "ollama",
        "model": model,
        "url": url,
        "temperature": temperature,
    }

    LOGGER.info("Calling Ollama model=%s", model)

    req = urllib.request.Request(
        url,
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        meta.update(
            {
                "status": "error",
                "error_type": "http_error",
                "http_status": getattr(exc, "code", None),
                "error_message": str(exc),
                "error_body_preview": body[:800],
            }
        )
        raise RuntimeError(f"Ollama HTTP error: {exc}") from exc
    except urllib.error.URLError as exc:
        meta.update(
            {
                "status": "error",
                "error_type": "url_error",
                "error_message": str(exc),
            }
        )
        raise RuntimeError(f"Ollama URL error: {exc}") from exc
    except Exception as exc:
        meta.update(
            {
                "status": "error",
                "error_type": "request_error",
                "error_message": str(exc),
            }
        )
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    meta["raw_response_preview"] = raw[:800]
    LOGGER.debug("Ollama raw response preview: %s", raw[:800])

    try:
        outer = json.loads(raw)
    except json.JSONDecodeError as exc:
        meta.update(
            {
                "status": "error",
                "error_type": "outer_json_decode_error",
                "error_message": str(exc),
            }
        )
        raise RuntimeError(f"Ollama outer JSON invalid: {exc}") from exc

    model_text = str(outer.get("message", {}).get("content", "")).strip()
    meta["model_text_preview"] = model_text[:800]
    LOGGER.debug("Ollama model_text preview: %s", model_text[:800])

    hints, extraction_mode = _coerce_hints(model_text, expected_count=N_HINTS)

    meta.update(
        {
            "status": "ok" if hints else "empty",
            "parsed_hint_count": len(hints),
            "extraction_mode": extraction_mode,
            "reason": "" if hints else "no_valid_hints_in_model_json",
        }
    )

    if not hints:
        LOGGER.warning("Ollama returned 0 valid hints after parsing")

    return hints, meta


def generate_candidate_hints(
    prompt: str,
    verdict: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.5,
) -> list[str]:
    ollama_meta: dict[str, Any] | None = None
    openai_meta: dict[str, Any] | None = None

    try:
        hints, ollama_meta = _generate_with_ollama(prompt, temperature=temperature)
        if hints:
            _set_last_generation_debug(
                {
                    "status": "ok",
                    "source": "ollama",
                    "details": ollama_meta,
                }
            )
            LOGGER.info("Hints generated from Ollama model=%s", ollama_meta.get("model"))
            return hints

        LOGGER.warning("Ollama returned empty hints. details=%s", ollama_meta)
    except Exception as exc:
        LOGGER.exception("Ollama generation failed: %s", exc)
        if ollama_meta is None:
            ollama_meta = {
                "provider": "ollama",
                "status": "error",
                "error_message": str(exc),
            }

    _set_last_generation_debug(
        {
            "status": "fallback",
            "source": "fallback",
            "reason": "no_valid_hints_from_ollama_or_openai",
            "ollama_attempt": ollama_meta,
            "openai_attempt": openai_meta,
            "fallback_language": "ro",
        }
    )
    LOGGER.error("Fallback hints used. Cause saved in get_last_generation_debug().")
    print("No hints generated. Using fallback hints.")