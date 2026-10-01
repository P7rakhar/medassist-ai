"""
Simpler systems to compare MedAssist AI against, on the same 60 cases (used by run_eval.py).

  keyword      Plain keyword matching: a symptom counts if any of its phrases appears in the text.
               No spelling tolerance, no transliteration, no body-part composer, no negation or
               "maybe / in the past" handling, no duration / age / temperature. This is how a
               typical simple symptom checker works.
  no_context   The full MedAssist pipeline with ONLY the ConText step switched off, so every
               symptom mentioned counts as present ("no fever" -> fever). This isolates what the
               negation / uncertainty / history engine contributes (an ablation study).

Both feed the SAME knowledge graph, risk scoring and triage rules, so the difference in the
numbers comes from understanding the text, nothing else.
"""
from __future__ import annotations

import re
from datetime import datetime

from backend.nlp import Extraction, Mention
from backend.pipeline import MedAssistEngine


class KeywordExtractor:
    """Case-insensitive whole-word keyword matching over the knowledge graph's phrase lists."""

    def __init__(self, symptoms: dict):
        self.patterns: list[tuple[str, re.Pattern]] = []
        for sid, s in symptoms.items():
            for lang in ("en", "hi", "hinglish"):
                for phrase in s.get(lang, []):
                    p = re.escape(phrase.lower())
                    # \b works for Latin script; Devanagari phrases are matched as plain substrings.
                    pat = rf"\b{p}\b" if phrase.isascii() else p
                    self.patterns.append((sid, re.compile(pat)))

    def extract(self, text: str, now: datetime | None = None) -> Extraction:
        low = text.lower()
        out = Extraction()
        seen = set()
        for sid, pat in self.patterns:
            m = pat.search(low)
            if m and sid not in seen:
                seen.add(sid)
                out.mentions.append(Mention(sid, m.group(0), method="keyword"))
        return out


def keyword_engine() -> MedAssistEngine:
    eng = MedAssistEngine()
    eng.extractor = KeywordExtractor(eng.kg.symptoms)
    return eng


def no_context_engine() -> MedAssistEngine:
    eng = MedAssistEngine()
    eng.extractor.context.apply = lambda keys, spans: []     # every mention stays "present"
    return eng
