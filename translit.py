"""
Script and spelling robustness for Indian-language input.

1. `deva_to_roman()` transliterates Devanagari (Hindi) into Roman letters using
   a rule-based scheme with Hindi schwa deletion (धड़कन -> dhadkan, बुखार -> bukhaar).
2. `phonetic_key()` collapses common Hinglish spelling variants to one key
   (bukhaar / bukhar / bukar -> "bukar", khaansee / khansi -> "kansi").

Every lexicon phrase AND every input word is reduced to the same key, so
Hindi typed in Devanagari, Hinglish typed in any spelling, and the lexicon all
meet in one shared space. Pure Python, no dependencies.
"""
from __future__ import annotations

import re

VOWELS = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
          "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au"}
MATRAS = {"ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au"}
CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
}
VIRAMA, ANUSVARA, CHANDRABINDU, VISARGA, NUKTA = "्", "ं", "ँ", "ः", "़"
DIGITS = {chr(0x0966 + i): str(i) for i in range(10)}  # ० १ २ ... -> 0 1 2


def is_devanagari(text: str) -> bool:
    return any(0x0900 <= ord(ch) <= 0x097F for ch in text)


def deva_to_roman(word: str) -> str:
    """Transliterate one Devanagari word. Non-Devanagari characters pass through."""
    units: list[list] = []      # [consonant_roman, vowel_roman | None(=inherent a) | "" (virama)]
    out_tail = []
    i = 0
    while i < len(word):
        ch = word[i]
        if ch in CONSONANTS:
            unit = [CONSONANTS[ch], None]
            j = i + 1
            if j < len(word) and word[j] == NUKTA:
                j += 1
            if j < len(word) and word[j] in MATRAS:
                unit[1] = MATRAS[word[j]]; j += 1
            elif j < len(word) and word[j] == VIRAMA:
                unit[1] = ""; j += 1
            units.append(unit)
            i = j
        elif ch in VOWELS:
            units.append(["", VOWELS[ch]]); i += 1
        elif ch in (ANUSVARA, CHANDRABINDU):
            units.append(["n", ""]); i += 1
        elif ch == VISARGA:
            units.append(["h", ""]); i += 1
        elif ch in DIGITS:
            units.append([DIGITS[ch], ""]); i += 1
        elif ch == NUKTA:
            i += 1
        else:
            units.append([ch, ""]); i += 1

    # Schwa deletion: word-final inherent 'a' is silent; a medial one is silent in a V C _ C V context.
    def has_vowel(u):
        return u[1] is None or u[1] != ""

    consonant_idx = [k for k, u in enumerate(units) if u[0] and u[0] not in "0123456789" and u[1] is None]
    if consonant_idx and consonant_idx[-1] == len(units) - 1 and len(units) > 1:
        units[-1][1] = ""
    for k in range(1, len(units) - 1):
        u = units[k]
        if u[1] is None and has_vowel(units[k - 1]) and units[k + 1][0] and has_vowel(units[k + 1]) and k + 1 < len(units) - 1:
            u[1] = ""
    return "".join(c + ("a" if v is None else v) for c, v in units) + "".join(out_tail)


_CLUSTERS = [("chh", "ch"), ("ph", "f"), ("kh", "k"), ("gh", "g"), ("jh", "j"), ("th", "t"), ("dh", "d"),
             ("bh", "b"), ("sh", "s"), ("ck", "k"), ("w", "v"), ("z", "j"), ("q", "k"), ("x", "ks"),
             ("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u")]
CANONICAL = {"mein": "me", "mai": "me", "mei": "me", "men": "me", "main": "main", "me": "me",
             "nahin": "nahi", "nai": "nahi", "nhi": "nahi", "nahee": "nahi", "nahii": "nahi"}


_POST_CANONICAL = {"nahin": "nahi", "nai": "nahi", "nhi": "nahi", "mein": "me", "mai": "me", "mei": "me", "men": "me"}


def phonetic_key(token: str) -> str:
    """Reduce a (romanised) word to a spelling-tolerant key."""
    if not token:
        return token
    if is_devanagari(token):
        token = deva_to_roman(token)
    w = token.lower()
    w = CANONICAL.get(w, w)
    if not re.search(r"[a-z]", w):
        return w
    for a, b in _CLUSTERS:
        w = w.replace(a, b)
    w = re.sub(r"(.)\1+", r"\1", w)          # chakkar -> chakar, ulti stays
    if len(w) > 3 and w.endswith("y"):
        w = w[:-1] + "i"
    return _POST_CANONICAL.get(w, w)


def key_tokens(tokens: list[str]) -> tuple[str, ...]:
    return tuple(phonetic_key(t) for t in tokens)
