"""
OPTIONAL LLM fallback (off by default — the app works fully offline without it).

When the offline lexicon finds no symptoms (e.g. an unusual phrasing, or a
language we don't have a lexicon for yet, such as Tamil), the text can be sent
to any OpenAI-compatible chat API (Groq / Llama 3, OpenAI, a local Ollama...).

Safety design: the LLM is used ONLY to translate free text into symptom IDs
from our own knowledge graph. Its output is filtered against that whitelist,
and the diagnosis, triage and doctor matching are still done by our
deterministic, auditable engine. The LLM never gives medical advice.

Enable by setting environment variables before starting the server:
    MEDASSIST_LLM_API_KEY   = <your key>
    MEDASSIST_LLM_BASE_URL  = https://api.groq.com/openai/v1   (default)
    MEDASSIST_LLM_MODEL     = llama-3.1-8b-instant             (default)
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

SYSTEM_PROMPT = (
    "You convert a patient's description of their health problem (any language) into symptom IDs. "
    "Only use IDs from the provided list. Ignore symptoms the patient says they do NOT have. "
    'Reply with JSON only, e.g. {"symptoms": ["fever", "cough"]}. If nothing matches, reply {"symptoms": []}.'
)


def enabled() -> bool:
    return bool(os.environ.get("MEDASSIST_LLM_API_KEY"))


def config_summary() -> dict:
    return {"enabled": enabled(),
            "model": os.environ.get("MEDASSIST_LLM_MODEL", "llama-3.1-8b-instant") if enabled() else None}


def extract_symptom_ids(text: str, allowed: dict[str, str], timeout: float = 8.0) -> tuple[list[str], str]:
    """Return (symptom_ids, status_message). Never raises."""
    if not enabled():
        return [], "LLM fallback disabled (offline mode)"
    base = os.environ.get("MEDASSIST_LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    model = os.environ.get("MEDASSIST_LLM_MODEL", "llama-3.1-8b-instant")
    catalogue = "\n".join(f"{sid}: {label}" for sid, label in allowed.items())
    body = {
        "model": model, "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Allowed symptom IDs:\n{catalogue}\n\nPatient said:\n{text}"},
        ],
    }
    req = urllib.request.Request(
        f"{base}/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['MEDASSIST_LLM_API_KEY']}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = json.loads(resp.read())["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", content, re.S)
        ids = json.loads(match.group(0)).get("symptoms", []) if match else []
        valid = [s for s in ids if s in allowed]          # whitelist: drop anything invented
        return list(dict.fromkeys(valid)), f"LLM ({model}) mapped text to {len(valid)} symptom(s)"
    except Exception as exc:  # network down, bad key, bad JSON -> degrade gracefully
        return [], f"LLM fallback unavailable ({type(exc).__name__}); used offline engine only"
