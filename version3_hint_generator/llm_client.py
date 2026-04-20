from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from config import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL

LOGGER = logging.getLogger("v3_hint_generator")
if not LOGGER.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    LOGGER.addHandler(_h)
LOGGER.setLevel(logging.DEBUG)


def ollama_chat(
    user_prompt: str,
    system_prompt: str = "Return only valid JSON. No explanations.",
    temperature: float = 0.5,
    json_format: bool = True,
    timeout: int = 180,
) -> str:
    """Call Ollama /api/chat and return the model's response string."""
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    url = f"{base_url}/api/chat"

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": temperature},
    }
    if json_format:
        payload["format"] = "json"

    LOGGER.info("Calling Ollama model=%s url=%s", model, url)
    LOGGER.debug("System prompt:\n%s", system_prompt)
    LOGGER.debug("User prompt:\n%s", user_prompt)

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        LOGGER.error("Ollama HTTP error %s: %s", exc.code, body[:400])
        raise RuntimeError(f"Ollama HTTP {exc.code}: {body[:200]}") from exc
    except urllib.error.URLError as exc:
        LOGGER.error("Ollama URL error: %s", exc)
        raise RuntimeError(f"Ollama not reachable: {exc}") from exc

    LOGGER.debug("Ollama raw response preview: %s", raw[:600])

    outer = json.loads(raw)
    content = str(outer.get("message", {}).get("content", "")).strip()
    LOGGER.debug("Model content preview: %s", content[:600])
    return content


def parse_json_response(text: str) -> dict[str, Any]:
    """Robustly parse a JSON object from an LLM response string."""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for fence in ("```json", "```"):
        if fence in text:
            start = text.find(fence) + len(fence)
            end = text.rfind("```")
            if end > start:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    LOGGER.warning("Could not parse JSON from model response: %s", text[:400])
    return {}
