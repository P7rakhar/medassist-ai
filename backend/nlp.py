"""
NLP layer: language detection, normalisation, and medical entity extraction.

Pipeline for every sentence (all offline, pure Python):

  1. normalise      Unicode NFC, nukta/chandrabindu unified, punctuation removed (commas kept as scope markers)
  2. phonetic keys  every word -> spelling-tolerant key; Devanagari transliterated first (translit.py)
  3. lexicon match  longest phrase first over 700+ trilingual symptom phrases, fuzzy fallback for typos
  4. composer       body part + sensation anywhere nearby ("my stomach hurts", "dard pet mein") (bodymap.py)
  5. ConText        negated / uncertain / historical / family-history attributes (context.py)
  6. slots          duration ("3 din se", "since Monday"), severity words, pain score "8/10",
                    temperature "103 F", age "I am 67"
  7. coverage       words we did NOT understand are reported, so gaps are visible

An LLM can optionally be plugged in as a fallback (llm.py), but it can only map
text onto symptom IDs that already exist in our knowledge graph.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from .bodymap import PART_INDEX, SENSE_INDEX, compose
from .context import ConTextEngine, Span
from .translit import phonetic_key

DATA = Path(__file__).parent / "data"

# ---------------------------------------------------------------- language ---

SCRIPT_RANGES = {
    "hi": (0x0900, 0x097F),   # Devanagari (Hindi, Marathi, Nepali...)
    "bn": (0x0980, 0x09FF),   # Bengali
    "pa": (0x0A00, 0x0A7F),   # Gurmukhi (Punjabi)
    "gu": (0x0A80, 0x0AFF),   # Gujarati
    "ta": (0x0B80, 0x0BFF),   # Tamil
    "te": (0x0C00, 0x0C7F),   # Telugu
    "kn": (0x0C80, 0x0CFF),   # Kannada
    "ml": (0x0D00, 0x0D7F),   # Malayalam
}
LANG_NAMES = {
    "en": "English", "hi": "Hindi", "hinglish": "Hinglish (Hindi in Roman script)",
    "bn": "Bengali", "pa": "Punjabi", "gu": "Gujarati", "ta": "Tamil",
    "te": "Telugu", "kn": "Kannada", "ml": "Malayalam",
}
# Common Hindi function words / symptom words written in Roman script.
HINGLISH_MARKERS = {
    "mujhe", "mera", "meri", "mere", "hai", "hain", "ho", "raha", "rahi", "rahe",
    "nahi", "nahin", "bahut", "bohot", "aur", "se", "ka", "ki", "ke", "mein",
    "kal", "din", "hafte", "dard", "bukhar", "pet", "sir", "sar", "khansi",
    "ulti", "saans", "jalan", "chakkar", "thakan", "kamzori", "kya", "bhi",
    "tha", "thi", "gaya", "gayi", "lag", "lagti", "laga", "hua", "hui",
    "zukam", "jukam", "dast", "pasina", "gala", "gale", "aankh", "seene",
}


def detect_language(text: str) -> dict:
    """Detect language from Unicode script, then Hinglish markers for Roman text."""
    counts = {code: 0 for code in SCRIPT_RANGES}
    latin = 0
    for ch in text:
        cp = ord(ch)
        if ("a" <= ch.lower() <= "z"):
            latin += 1
            continue
        for code, (lo, hi) in SCRIPT_RANGES.items():
            if lo <= cp <= hi:
                counts[code] += 1
                break
    total = latin + sum(counts.values())
    if total == 0:
        return {"code": "en", "name": LANG_NAMES["en"], "confidence": 0.0}

    best_indic = max(counts, key=counts.get)
    if counts[best_indic] > latin:
        conf = counts[best_indic] / total
        return {"code": best_indic, "name": LANG_NAMES[best_indic], "confidence": round(conf, 2)}

    words = re.findall(r"[a-z]+", text.lower())
    hits = sum(1 for w in words if w in HINGLISH_MARKERS)
    ratio = hits / max(len(words), 1)
    if hits >= 2 and ratio >= 0.15:
        return {"code": "hinglish", "name": LANG_NAMES["hinglish"], "confidence": round(min(1.0, 0.5 + ratio), 2)}
    return {"code": "en", "name": LANG_NAMES["en"], "confidence": round(1.0 - ratio, 2)}


# ------------------------------------------------------------ normalisation ---

_SENTENCE_SPLIT = re.compile(r"[.!?।;\n]+(?!\d)")
_PUNCT = re.compile(r"[\"'’`()\[\]{}:/\\\-–—_*#@~+=<>!?।|;]|(?<!\d)\.|\.(?!\d)")


def normalise(text: str, keep_commas: bool = False) -> str:
    """Lower-case, unify Unicode variants (nukta, chandrabindu), strip punctuation."""
    text = unicodedata.normalize("NFC", text).lower()
    text = text.replace("़", "")          # nukta: ज़ -> ज
    text = text.replace("ँ", "ं")    # chandrabindu -> anusvara: आँ -> आं
    text = text.replace("’", "'")
    text = re.sub(r"\b(can|don|didn|isn|doesn|haven|won|aren|wasn|hasn)'t\b", lambda m: m.group(1) + "t", text)
    text = re.sub(r"\bi'm\b", "im", text)
    text = re.sub(r"(\d+)\s*/\s*10\b", r"\1 outof 10", text)        # keep pain scores "8/10"
    text = _PUNCT.sub(" ", text)
    text = text.replace(",", " , ") if keep_commas else text.replace(",", " ")
    return re.sub(r"\s+", " ", text).strip()


def sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]


# ------------------------------------------------------------- slot values ---

SEVERE_CUES = {phonetic_key(w) for w in [
    "severe", "very", "unbearable", "extreme", "extremely", "terrible", "worst", "intense", "really", "excruciating",
    "bad", "badly", "awful", "horrible", "kaafi", "kafi", "kaafi zyada",
    "bahut", "bohot", "bahot", "tez", "tej", "zyada", "jyada", "bhayankar", "asahniya",
    "बहुत", "तेज", "ज्यादा", "असहनीय", "भयंकर"]}
MILD_CUES = {phonetic_key(w) for w in [
    "mild", "slight", "slightly", "little", "bit", "halka", "halki", "thoda", "thodi", "हल्का", "हल्की", "थोडा", "थोडी"]}

NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "ten": 10, "few": 3, "couple": 2, "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4,
    "paanch": 5, "panch": 5, "saat": 7, "das": 10,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "सात": 7, "दस": 10,
}
UNIT_DAYS = {
    "hour": 1 / 24, "hours": 1 / 24, "hrs": 1 / 24, "ghante": 1 / 24, "ghanta": 1 / 24, "घंटे": 1 / 24,
    "day": 1, "days": 1, "din": 1, "dino": 1, "dinon": 1, "दिन": 1, "दिनों": 1,
    "week": 7, "weeks": 7, "hafte": 7, "hafta": 7, "hafton": 7, "हफ्ते": 7, "हफ्ता": 7, "सप्ताह": 7,
    "month": 30, "months": 30, "mahine": 30, "mahina": 30, "महीने": 30, "महीना": 30,
    "year": 365, "years": 365, "saal": 365, "sal": 365, "साल": 365, "वर्ष": 365,
}
_DURATION_RE = re.compile(
    r"(?<!\S)(\d+(?:\.\d+)?|" + "|".join(sorted(map(re.escape, NUM_WORDS), key=len, reverse=True)) + r")\s+(?:of\s+)?("
    + "|".join(sorted(map(re.escape, UNIT_DAYS), key=len, reverse=True)) + r")(?=\s|$)"
)
_RELATIVE_DURATION = [
    (re.compile(r"for (?:many |several |a few )?months|since months|mahinon se|kai mahine|महीनों से|कई महीने"), 60.0),
    (re.compile(r"for (?:many |several |a few )?weeks|since weeks|hafton se|kai hafte|हफ्तों से|कई हफ्ते"), 14.0),
    (re.compile(r"for (?:many |several )?days|since days|kai din|dino se|कई दिन|दिनों से"), 4.0),
    (re.compile(r"day before yesterday|parso se|parson se|परसों से"), 2.0),
    (re.compile(r"since yesterday|from yesterday|kal se|कल से|last night|kal raat"), 1.0),
    (re.compile(r"since morning|since today|aaj se|subah se|आज से|सुबह से|this morning|since last night"), 0.5),
]
WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
            "somvar": 0, "mangalvar": 1, "budhvar": 2, "guruvar": 3, "shukravar": 4, "shanivar": 5, "ravivar": 6,
            "सोमवार": 0, "मंगलवार": 1, "बुधवार": 2, "गुरुवार": 3, "शुक्रवार": 4, "शनिवार": 5, "रविवार": 6}
_WEEKDAY_RE = re.compile(r"(?:since|from)\s+(?:last\s+)?(" + "|".join(WEEKDAYS) + r")|(" + "|".join(WEEKDAYS) + r")\s+(?:se|से)")
_TEMP_RE = re.compile(r"\b(\d{2,3}(?:\.\d)?)\s*(?:°|deg|degree|degrees|डिग्री)?\s*(f|fahrenheit|c|celsius)?\b")
# A bare number only counts as a temperature next to a temperature word ("fever of 102", "temperature 38.5",
# "102 bukhar"), never as an age, heart rate or blood pressure ("40-year-old", "105 bpm").
_TEMP_BEFORE = re.compile(r"(?:temperature|temp|fever|fevers|febrile|bukhar|bukhaar|taap|बुखार|ताप|तापमान)\s*(?:of|to|is|was|as high as|=|:|hai|ka|का)?\s*(?:about|around|upto|up to)?\s*$")
_TEMP_AFTER = re.compile(r"^\s*(?:°|deg|degree|degrees|डिग्री)?\s*(?:f|c)?\s*(?:fever|bukhar|bukhaar|बुखार|ka bukhar|का बुखार)")
_NOT_TEMP_AFTER = re.compile(r"^\s*(?:year|years|yr|yrs|month|months|week|weeks|day|days|hour|hours|bpm|beats|mm|mmhg|percent|%|kg|cm|saal|din|साल|दिन|breaths|per)")
# Oxygen saturation from a pulse oximeter: "SpO2 91%", "oxygen saturation of 92 percent", "oxygen level 90".
_SPO2_RE = re.compile(r"(?:spo2|sp o2|spo 2|oxygen saturation|o2 saturation|o2 sat|oxygen sat|saturation|oxygen level|oxygen)\D{0,25}?(\d{2,3})\s*(?:%|percent)?")
_PAIN_SCORE_RE = re.compile(r"\b(\d{1,2})\s*(?:outof|out of|on|me se|mein se|में से)\s*10\b")
# Age needs explicit context ("I am 65", "65 years old", "65 saal ka") so that
# "headache for 2 years" is read as a duration, not an age.
_AGE_RE = re.compile(
    r"(?<!\S)(?:i am|i m|im|age|aged|umar|umr|उम्र)\s+(?:is\s+)?(\d{1,3})(?!\S)"
    r"|(?<!\S)(\d{1,3})\s*(?:years?|yrs?|yr|saal|sal|साल|वर्ष)\s+(?:old|ka|ki|का|की|के)(?!\S)"
)

# Words that carry no symptom meaning; they are "understood" for coverage reporting.
STOPWORDS = {phonetic_key(w) for w in """
i im me my mine we our you your he she his her it its they them this that these those a an the and or but so
is am are was were be been being have has had having do does did doing get got getting feel feeling felt
in on at of for from to with by since about after before during into over under again also very too just
some any much many more most lot lots little bit really now today yesterday tonight morning evening night week day days
please help doctor sir madam hello hi thanks thank what why how when which who where can could would should will
also both all every each other same such own only than then there here up down out off dono donon
mujhe mera meri mere hum hamara humein aap aapka tum hai hain ho hu hoon tha thi the raha rahi rahe rha rhi gaya gayi
ka ki ke ko se me mein par pe tak bhi aur ya to toh kya kyon kaise kab jab tab ab abhi kuch bahut bohot sab
ek do teen char din kal aaj subah shaam raat hafte mahine saal se lag laga lagi lagta lagti hua hui hue kar karta
मुझे मेरा मेरी मेरे हम आप है हैं हो हूं था थी थे रहा रही रहे गया गई का की के को से में पर तक भी और या तो क्या
कुछ बहुत सब एक दो तीन दिन कल आज सुबह शाम रात हफ्ते महीने साल लग लगा लगी लगता लगती हुआ हुई कर करता""".split()}


@dataclass
class Mention:
    symptom_id: str             # a symptom ID, or a risk-factor / condition ID when kind != "symptom"
    text: str
    negated: bool = False
    kind: str = "symptom"       # symptom | risk | condition
    method: str = "lexicon"     # lexicon | fuzzy | composed | rule | chip | answer | llm
    score: float = 1.0
    uncertain: bool = False
    historical: bool = False
    family: bool = False
    trigger: str | None = None  # the context phrase that modified it

    @property
    def active(self) -> bool:
        return self.kind == "symptom" and not (self.negated or self.historical or self.family)


@dataclass
class Extraction:
    mentions: list[Mention] = field(default_factory=list)
    duration_days: float | None = None
    severity: str = "normal"              # "mild" | "normal" | "severe"
    pain_score: int | None = None
    temperature_f: float | None = None
    spo2: int | None = None                       # pulse-oximeter oxygen saturation, %
    age: int | None = None
    tokens: list[str] = field(default_factory=list)
    unrecognised: list[str] = field(default_factory=list)
    triggers: list[dict] = field(default_factory=list)
    unplaced_sensations: list[str] = field(default_factory=list)   # "pain" with no body part

    @property
    def present(self) -> list[str]:
        return list(dict.fromkeys(m.symptom_id for m in self.mentions if m.active))

    @property
    def weights(self) -> dict[str, float]:
        """1.0 for certain symptoms, 0.5 when every mention of it was uncertain ("maybe fever")."""
        w: dict[str, float] = {}
        for m in self.mentions:
            if m.active:
                w[m.symptom_id] = max(w.get(m.symptom_id, 0.0), 0.5 if m.uncertain else 1.0)
        return w

    @property
    def uncertain(self) -> list[str]:
        return [s for s, w in self.weights.items() if w < 1.0]

    def _only(self, attr: str) -> list[str]:
        pos = set(self.present)
        return list(dict.fromkeys(m.symptom_id for m in self.mentions
                                  if m.kind == "symptom" and getattr(m, attr) and m.symptom_id not in pos))

    @property
    def risk_factors(self) -> list[dict]:
        """Existing conditions that raise risk (diabetes, pregnancy...). Past ones count; denied or family ones don't."""
        out = {}
        for m in self.mentions:
            if m.kind == "risk" and not m.negated and not m.family:
                out.setdefault(m.symptom_id, {"id": m.symptom_id, "text": m.text})
        return list(out.values())

    @property
    def family_history(self) -> list[str]:
        return list(dict.fromkeys(m.symptom_id for m in self.mentions if m.kind in ("risk", "condition") and m.family))

    @property
    def condition_mentions(self) -> list[dict]:
        """Diseases the person named themselves ("I think it's dengue", "had typhoid last year")."""
        out = {}
        for m in self.mentions:
            if m.kind == "condition" and not m.family:
                status = "denied" if m.negated else "past" if m.historical else "suspected" if m.uncertain else "stated"
                out.setdefault(m.symptom_id, {"id": m.symptom_id, "text": m.text, "status": status})
        return list(out.values())

    @property
    def absent(self) -> list[str]:
        return self._only("negated")

    @property
    def historical(self) -> list[str]:
        return self._only("historical")

    @property
    def family(self) -> list[str]:
        return self._only("family")


class SymptomExtractor:
    """Lexicon + composer + ConText extractor over spelling-tolerant phonetic keys."""

    FUZZY_THRESHOLD = 0.86

    def __init__(self, symptoms: dict, triggers_path: str | Path = DATA / "context_triggers.json",
                 risk_factors: dict | None = None, condition_names: dict | None = None):
        self.index: dict[tuple[str, ...], str] = {}
        self.kind: dict[str, str] = {}

        def add(entry_id: str, phrases: list[str], kind: str):
            for phrase in phrases:
                keys = tuple(phonetic_key(t) for t in normalise(phrase).split())
                if keys and keys not in self.index:
                    self.index[keys] = f"{kind}:{entry_id}"

        for sid, entry in symptoms.items():
            add(sid, [p for lang in ("en", "hi", "hinglish") for p in entry.get(lang, [])], "symptom")
        for rid, entry in (risk_factors or {}).items():
            add(rid, [p for lang in ("en", "hi", "hinglish") for p in entry.get(lang, [])], "risk")
        for cid, names in (condition_names or {}).items():
            add(cid, names, "condition")
        self.max_n = max(len(k) for k in self.index)
        self.fuzzy_by_n: dict[int, list[tuple[str, str]]] = {}
        for keys, ref in self.index.items():
            joined = " ".join(keys)
            if ref.startswith("symptom:") and joined.isascii() and len(joined) >= 5:
                self.fuzzy_by_n.setdefault(len(keys), []).append((joined, ref))
        self.context = ConTextEngine(triggers_path)
        self.vocab = set(STOPWORDS) | {k for key in PART_INDEX for k in key} | {k for key in SENSE_INDEX for k in key} \
            | {phonetic_key(w) for w in list(NUM_WORDS) + list(UNIT_DAYS) + list(WEEKDAYS)} | SEVERE_CUES | MILD_CUES \
            | {k for key in self.context.triggers for k in key} | {"outof", "years", "old", "saal", "age"}

    # ---- matching -------------------------------------------------------
    def _lexicon_spans(self, keys: list[str]) -> list[tuple[int, int, str, str, float]]:
        spans, i = [], 0
        while i < len(keys):
            if keys[i] == ",":
                i += 1; continue
            hit = None
            for n in range(min(self.max_n, len(keys) - i), 0, -1):
                window = keys[i:i + n]
                if "," in window:
                    continue
                if tuple(window) in self.index:
                    hit = (i, i + n, self.index[tuple(window)], "lexicon", 1.0)
                    break
            if hit is None:
                for n in range(min(3, len(keys) - i), 0, -1):
                    window = keys[i:i + n]
                    joined = " ".join(window)
                    if "," in window or not joined.isascii() or len(joined) < 5 or joined in self.vocab:
                        continue
                    threshold = self.FUZZY_THRESHOLD if n == 1 else 0.9
                    best = (0.0, None)
                    for cand, sid in self.fuzzy_by_n.get(n, []):
                        if abs(len(cand) - len(joined)) > 3:            # cheap length filter first
                            continue
                        sm = SequenceMatcher(None, joined, cand)
                        if sm.real_quick_ratio() < threshold or sm.quick_ratio() < threshold:
                            continue
                        r = sm.ratio()
                        if r > best[0]:
                            best = (r, sid)
                    if best[0] >= threshold:
                        hit = (i, i + n, best[1], "fuzzy", round(best[0], 2))
                        break
            if hit:
                spans.append(hit); i = hit[1]
            else:
                i += 1
        return spans

    # ---- main entry -----------------------------------------------------
    def extract(self, text: str, now: datetime | None = None) -> Extraction:
        # "confused about which medicine" is uncertainty, not the medical sign "confusion".
        text = re.sub(r"\bconfused\s+(about|which|whether|if|regarding|by|with)\b", r"unsure \1", text, flags=re.I)
        out = Extraction()
        norm_full = normalise(text)
        out.tokens = norm_full.split()
        severity_votes = {"severe": 0, "mild": 0}
        understood_tokens: set[str] = set()

        for sentence in sentences(text):
            raw = normalise(sentence, keep_commas=True).split()
            keys = [t if t == "," else phonetic_key(t) for t in raw]
            lex = self._lexicon_spans(keys)
            covered = {k for s in lex for k in range(s[0], s[1])}
            comp, unplaced = compose(keys, covered)
            out.unplaced_sensations += [u for u in unplaced if u not in out.unplaced_sensations]
            spans = [Span(s, e) for s, e, *_ in lex] + [Span(s, e, inner_gaps=inner) for s, e, _, inner in comp]
            meta = [(ref, method, score) for _, _, ref, method, score in lex] + [(f"symptom:{sid}", "composed", 1.0) for *_, sid, _ in comp]
            hits = self.context.apply(keys, spans)

            for span, (ref, method, score) in zip(spans, meta):
                kind, sid = ref.split(":", 1)
                mods = span.modifiers
                trig = next(iter(mods.values()), None)
                out.mentions.append(Mention(
                    sid, " ".join(t for t in raw[span.start:span.end] if t != ","), negated="NEGATED" in mods, kind=kind,
                    method=method, score=score, uncertain="UNCERTAIN" in mods, historical="HISTORICAL" in mods,
                    family="FAMILY" in mods, trigger=trig))
            for h in hits:
                out.triggers.append({"category": h.category, "text": h.text})

            used = {k for s in spans for k in range(s.start, s.end)} | {k for h in hits for k in range(h.start, h.end)}
            any_active = any(not ({"NEGATED", "HISTORICAL", "FAMILY"} & set(sp.modifiers)) for sp, (ref, *_) in zip(spans, meta)
                             if ref.startswith("symptom:"))
            # severity words inside a fixed phrase ("tez bukhar" = high fever) are already counted by that phrase
            in_lexicon = {k for s, e, *_ in lex for k in range(s, e)}
            for k, key in enumerate(keys):
                if key == ",":
                    continue
                if k in used or key in self.vocab or key.replace(".", "").isdigit():
                    understood_tokens.add(raw[k])
                    if any_active and k not in in_lexicon:
                        severity_votes["severe"] += key in SEVERE_CUES
                        severity_votes["mild"] += key in MILD_CUES
                else:
                    out.unrecognised.append(raw[k])

        # Implied parent symptoms ("high fever" also means "fever").
        for m in list(out.mentions):
            parent = SYMPTOM_PARENTS.get(m.symptom_id)
            if parent and m.active:
                out.mentions.append(Mention(parent, m.text, method="rule", uncertain=m.uncertain))

        # Temperature, e.g. "fever of 103 F", "38.9 c", "102 बुखार".
        for tm in _TEMP_RE.finditer(norm_full):
            num, unit = tm.group(1), tm.group(2) or ""
            before, after = norm_full[max(0, tm.start() - 40):tm.start()], norm_full[tm.end():tm.end() + 20]
            if _NOT_TEMP_AFTER.match(norm_full[tm.start() + len(num):tm.start() + len(num) + 12]):
                continue
            if not unit and not (_TEMP_BEFORE.search(before) or _TEMP_AFTER.match(after)):
                continue
            val = float(num)
            temp_f = val * 9 / 5 + 32 if (unit in ("c", "celsius") or 35 <= val <= 43) else val
            if 95 <= temp_f <= 110:
                out.temperature_f = round(temp_f, 1)
                if temp_f >= 99.5:
                    out.mentions.append(Mention("fever", f"{num}{unit}", method="rule"))
                if temp_f >= 102:
                    out.mentions.append(Mention("high_fever", f"{num}{unit}", method="rule"))
                break

        m = _SPO2_RE.search(norm_full)
        if m and 50 <= int(m.group(1)) <= 100:
            out.spo2 = int(m.group(1))
        if re.search(r"\bafebrile\b", norm_full):              # clinical shorthand for "no fever"
            out.mentions.append(Mention("fever", "afebrile", negated=True, method="rule"))
            out.unrecognised = [w for w in out.unrecognised if w != "afebrile"]

        m = _PAIN_SCORE_RE.search(norm_full)
        if m and 0 <= int(m.group(1)) <= 10:
            out.pain_score = int(m.group(1))
            out.unrecognised = [w for w in out.unrecognised if w != "outof"]
        out.age = self._age(norm_full)
        out.duration_days = self._duration(_AGE_RE.sub(" ", norm_full), now or datetime.now())

        if out.pain_score is not None and out.pain_score >= 7:
            out.severity = "severe"
        elif out.pain_score is not None and out.pain_score <= 3:
            out.severity = "mild"
        elif severity_votes["severe"] > severity_votes["mild"]:
            out.severity = "severe"
        elif severity_votes["mild"] > severity_votes["severe"]:
            out.severity = "mild"

        # A cough lasting 2 weeks or more is a TB screening trigger in India's national guidelines.
        if out.duration_days is not None and out.duration_days >= 14 and "cough" in out.present:
            out.mentions.append(Mention("prolonged_cough", "cough ≥ 2 weeks", method="rule"))
        out.unrecognised = list(dict.fromkeys(out.unrecognised))
        return out

    @staticmethod
    def _duration(text: str, now: datetime) -> float | None:
        best = None
        for num, unit in _DURATION_RE.findall(text):
            n = float(num) if num[0].isdigit() else NUM_WORDS[num]
            days = n * UNIT_DAYS[unit]
            best = days if best is None else max(best, days)
        for pattern, days in _RELATIVE_DURATION:
            if pattern.search(text):
                best = days if best is None else max(best, days)
        m = _WEEKDAY_RE.search(text)
        if m:
            wd = WEEKDAYS[m.group(1) or m.group(2)]
            days = (now.weekday() - wd) % 7 or 7
            best = days if best is None else max(best, days)
        return round(best, 2) if best is not None else None

    @staticmethod
    def _age(text: str) -> int | None:
        m = _AGE_RE.search(text)
        if not m:
            return None
        age = int(m.group(1) or m.group(2))
        return age if 0 < age < 120 else None


# A more specific symptom also implies its general parent.
SYMPTOM_PARENTS = {
    "high_fever": "fever", "severe_headache": "headache", "one_sided_headache": "headache",
    "cough_phlegm": "cough", "lower_right_abd_pain": "abdominal_pain", "prolonged_cough": "cough",
    "blister_rash": "rash",
}
