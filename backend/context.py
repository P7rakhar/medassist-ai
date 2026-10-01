"""
ConText engine: decides whether each symptom mention is negated, uncertain,
historical (already resolved) or about a family member.

Algorithm: NegEx / ConText (Chapman et al. 2001; Harkema et al. 2009), the
standard rule-based method for clinical text, extended here with Hindi and
Hinglish trigger phrases. For every trigger phrase found in a sentence:

  forward trigger  ->  modifies symptom mentions that FOLLOW it
  backward trigger ->  modifies symptom mentions that PRECEDE it
  scope            ->  up to `scope_tokens` words, stopping early at a
                       termination phrase ("but", "lekin"), a sentence
                       boundary, a comma (unless the sentence is a list
                       joined by "or" / "ya"), and direction-specific stop
                       words ("I have" ends a forward scope; the Hindi copula
                       "hai" ends a backward scope).

Pseudo-triggers ("not going away", "nahi utar raha") are matched first and
neutralise the negation words inside them. Symptom phrases that contain a
negation word themselves ("bhookh nahi lagti", "can't sleep") are protected
because symptom spans are found before triggers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .translit import phonetic_key

CATEGORIES = ("NEGATED", "UNCERTAIN", "HISTORICAL", "FAMILY")


@dataclass
class TriggerHit:
    start: int
    end: int
    category: str          # NEGATED | UNCERTAIN | HISTORICAL | FAMILY | PSEUDO | TERMINATE
    direction: str         # forward | backward | both
    text: str


@dataclass
class Span:
    start: int
    end: int
    inner_gaps: list[int] = field(default_factory=list)   # token positions inside a composite span
    modifiers: dict[str, str] = field(default_factory=dict)  # category -> trigger text


class ConTextEngine:
    def __init__(self, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.scope = int(data.get("scope_tokens", 6))
        self.triggers: dict[tuple[str, ...], tuple[str, str, str]] = {}
        for cat in CATEGORIES + ("PSEUDO", "TERMINATE"):
            for direction, phrases in data.get(cat, {}).items():
                for phrase in phrases:
                    key = tuple(phonetic_key(t) for t in phrase.lower().replace("'", "").split())
                    if not key:
                        continue
                    prev = self.triggers.get(key)
                    if prev and prev[0] == cat and prev[1] != direction:
                        self.triggers[key] = (cat, "both", phrase)   # listed both ways, e.g. "last year"
                    else:
                        self.triggers.setdefault(key, (cat, direction, phrase))
        self.max_len = max(len(k) for k in self.triggers)
        self.forward_stop = {phonetic_key(w) for w in data.get("FORWARD_STOP_WORDS", [])}
        self.backward_stop = {phonetic_key(w) for w in data.get("BACKWARD_STOP_WORDS", [])}
        self.list_words = {phonetic_key(w) for w in data.get("LIST_WORDS", [])}

    def find_triggers(self, keys: list[str], blocked: set[int]) -> list[TriggerHit]:
        hits, i = [], 0
        while i < len(keys):
            if i in blocked or keys[i] == ",":
                i += 1
                continue
            found = None
            for n in range(min(self.max_len, len(keys) - i), 0, -1):
                window = range(i, i + n)
                if any(k in blocked or keys[k] == "," for k in window):
                    continue
                key = tuple(keys[i:i + n])
                if key in self.triggers:
                    cat, direction, text = self.triggers[key]
                    found = TriggerHit(i, i + n, cat, direction, text)
                    break
            if found:
                hits.append(found)
                i = found.end
            else:
                i += 1
        return hits

    def apply(self, keys: list[str], spans: list[Span]) -> list[TriggerHit]:
        """Annotate spans in place with modifiers. Returns the triggers found (for the trace)."""
        blocked = {k for s in spans for k in range(s.start, s.end) if k not in s.inner_gaps}
        hits = self.find_triggers(keys, blocked)
        is_list = any(k in self.list_words for k in keys)
        terminators = [h for h in hits if h.category == "TERMINATE"]

        def stopped(a: int, b: int, direction: str) -> bool:
            """Is there a scope breaker strictly between token positions a and b?"""
            for t in terminators:
                if a <= t.start < b:
                    return True
            for k in range(a, b):
                if keys[k] == "," and not is_list:
                    return True
                if direction == "forward" and keys[k] in self.forward_stop:
                    return True
                if direction == "backward" and keys[k] in self.backward_stop:
                    return True
            return False

        for h in hits:
            if h.category in ("PSEUDO", "TERMINATE"):
                continue
            for s in spans:
                # trigger inside a composite span ("head is not hurting")
                if s.start <= h.start and h.end <= s.end:
                    s.modifiers.setdefault(h.category, h.text)
                    continue
                if h.direction in ("forward", "both") and s.start >= h.end:
                    gap = s.start - h.end
                    # pronoun/verb stop words ("no fever and I have cough") only limit negation;
                    # "maybe I have fever" must still mark fever as uncertain.
                    mode = "forward" if h.category == "NEGATED" else "forward_soft"
                    if gap <= self.scope and not stopped(h.end, s.start, mode):
                        s.modifiers.setdefault(h.category, h.text)
                if h.direction in ("backward", "both") and s.end <= h.start:
                    gap = h.start - s.end
                    if gap <= self.scope and not stopped(s.end, h.start, "backward"):
                        s.modifiers.setdefault(h.category, h.text)
        return hits
