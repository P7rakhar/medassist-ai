"""
Clarifying questions: what should the app ask next?

Three kinds of question, asked in this priority order:

1. SAFETY screens. If a symptom could hide an emergency, ask about the danger sign
   first (chest pain -> pain spreading to the arm? sweating?). Safety beats efficiency.
2. INFORMATION GAIN. Treat the knowledge graph as a probabilistic model:
       P(condition)          = current relative likelihood of each candidate condition
       P(symptom | condition) = edge weight (capped at 0.9), 0.05 if the condition lacks that symptom
   For every unasked symptom we compute the expected drop in entropy of the condition
   distribution after hearing "yes" or "no", and ask the questions that would narrow
   down the possibilities the most (the approach used by symptom-checker apps).
3. MISSING DETAILS (slots): since when, how bad, age, and where the pain is when the
   person said "pain" without a body part.

Answers come back as {symptom_id: true/false}; "no" is recorded as a denied symptom,
which lowers the conditions that depend on it, so each round converges.
"""
from __future__ import annotations

import math

from .knowledge_graph import KnowledgeGraph

MAX_SYMPTOM_QUESTIONS = 3

SAFETY_SCREENS = [
    # (if any of these are present, ...) -> (ask about these danger signs), optional condition
    ({"chest_pain"}, ["radiating_pain", "sweating", "breathlessness"], None),
    ({"fever", "high_fever"}, ["bleeding_gums"], None),
    ({"severe_headache", "dizziness", "confusion"}, ["slurred_speech", "face_droop"], None),
    ({"headache"}, ["slurred_speech", "face_droop"], lambda ctx: (ctx["age"] or 0) >= 50 or ctx["severity"] == "severe"),
    ({"abdominal_pain"}, ["lower_right_abd_pain"], None),
    ({"vomiting", "diarrhea"}, ["dehydration_signs"], None),
    ({"breathlessness"}, ["chest_pain", "confusion"], None),
    ({"heat_exposure"}, ["confusion", "hot_dry_skin"], None),
    ({"yellow_eyes"}, ["confusion"], None),
    ({"cough"}, ["coughing_blood"], lambda ctx: (ctx["duration"] or 0) >= 7),
    ({"low_mood", "anxiety"}, ["suicidal"], None),
]

PROMPTS = {
    "symptom": {"en": "Do you also have: {label}?", "hi": "क्या आपको यह भी है: {label}?"},
    "duration": {"en": "Since when?", "hi": "कब से?"},
    "severity": {"en": "How bad is it?", "hi": "कितनी तकलीफ है?"},
    "age": {"en": "Age of the patient?", "hi": "मरीज़ की उम्र?"},
    "location": {"en": "Where is the pain?", "hi": "दर्द कहाँ है?"},
}
DURATION_OPTIONS = [
    {"value": 0.5, "en": "Today", "hi": "आज से"}, {"value": 2.5, "en": "2–3 days", "hi": "2–3 दिन"},
    {"value": 7, "en": "About a week", "hi": "लगभग एक हफ्ता"}, {"value": 21, "en": "More than 2 weeks", "hi": "2 हफ्ते से ज़्यादा"},
]
SEVERITY_OPTIONS = [
    {"value": "mild", "en": "Mild", "hi": "हल्की"}, {"value": "normal", "en": "Moderate", "hi": "मध्यम"},
    {"value": "severe", "en": "Severe", "hi": "बहुत तेज़"},
]
AGE_OPTIONS = [
    {"value": 3, "en": "Under 5", "hi": "5 से कम"}, {"value": 12, "en": "5–17", "hi": "5–17"},
    {"value": 35, "en": "18–59", "hi": "18–59"}, {"value": 65, "en": "60 or older", "hi": "60 या ज़्यादा"},
]
LOCATION_OPTIONS = [
    ("headache", "Head", "सिर"), ("abdominal_pain", "Stomach", "पेट"), ("chest_pain", "Chest", "सीना"),
    ("back_pain", "Back", "कमर / पीठ"), ("joint_pain", "Joints", "जोड़"), ("sore_throat", "Throat", "गला"),
    ("ear_pain", "Ear", "कान"), ("body_ache", "Whole body", "पूरा शरीर"),
]


def entropy(p: dict[str, float]) -> float:
    return -sum(v * math.log2(v) for v in p.values() if v > 0)


def _normalise(p: dict[str, float]) -> dict[str, float]:
    total = sum(p.values()) or 1.0
    return {k: v / total for k, v in p.items()}


def information_gain(kg: KnowledgeGraph, weights: dict[str, float], absent: list[str],
                     exclude: set[str], top_n_conditions: int = 8) -> list[tuple[str, float]]:
    """Return [(symptom_id, expected_information_gain_in_bits)] best first."""
    cands = kg.query(weights, absent, top_k=top_n_conditions)
    if len(cands) < 2:
        return []
    prior = _normalise({c.id: c.likelihood for c in cands})
    h0 = entropy(prior)
    pool = {s for c in cands for s in kg.conditions[c.id]["symptoms"]} - exclude
    scored = []
    for s in pool:
        p_s = {cid: min(0.9, kg.conditions[cid]["symptoms"].get(s, 0.0)) or 0.05 for cid in prior}
        p_yes = sum(prior[c] * p_s[c] for c in prior)
        if not 0 < p_yes < 1:
            continue
        post_yes = _normalise({c: prior[c] * p_s[c] for c in prior})
        post_no = _normalise({c: prior[c] * (1 - p_s[c]) for c in prior})
        gain = h0 - (p_yes * entropy(post_yes) + (1 - p_yes) * entropy(post_no))
        scored.append((s, round(gain, 4)))
    scored.sort(key=lambda x: -x[1])
    return scored


def next_questions(kg: KnowledgeGraph, weights: dict[str, float], absent: list[str], answered: set[str],
                   duration: float | None, severity: str, pain_score: int | None, age: int | None,
                   unplaced_sensations: list[str], level: str, slots_answered: set[str]) -> list[dict]:
    present = set(weights)
    known = present | set(absent) | answered
    ctx = {"age": age, "severity": severity, "duration": duration}
    label = lambda s: {"en": kg.label(s, "en"), "hi": kg.label(s, "hi")}
    questions: list[dict] = []

    if unplaced_sensations and "location" not in slots_answered:
        questions.append({"type": "location", "prompt": PROMPTS["location"],
                          "options": [{"symptom": sid, "en": en, "hi": hi} for sid, en, hi in LOCATION_OPTIONS]})

    # 1. safety screens (a red flag already firing makes them moot)
    if level != "HIGH":
        for trigger, asks, cond in SAFETY_SCREENS:
            if present & trigger and (cond is None or cond(ctx)):
                for s in asks:
                    if s not in known and all(q.get("id") != s for q in questions) and len(questions) < 2:
                        questions.append({"type": "symptom", "id": s, "reason": "safety", "label": label(s),
                                          "prompt": PROMPTS["symptom"]})

    # 2. information gain
    if present and level != "HIGH":
        asked = {q.get("id") for q in questions}
        for s, gain in information_gain(kg, weights, absent, known | asked):
            if sum(q["type"] == "symptom" for q in questions) >= MAX_SYMPTOM_QUESTIONS or gain < 0.05:
                break
            questions.append({"type": "symptom", "id": s, "reason": "information_gain", "gain_bits": gain,
                              "label": label(s), "prompt": PROMPTS["symptom"]})

    # 3. missing details
    if present:
        if duration is None and "duration" not in slots_answered:
            questions.append({"type": "slot", "slot": "duration", "prompt": PROMPTS["duration"], "options": DURATION_OPTIONS})
        if severity == "normal" and pain_score is None and "severity" not in slots_answered:
            questions.append({"type": "slot", "slot": "severity", "prompt": PROMPTS["severity"], "options": SEVERITY_OPTIONS})
        if age is None and "age" not in slots_answered and level in ("MODERATE", "HIGH", "LOW"):
            questions.append({"type": "slot", "slot": "age", "prompt": PROMPTS["age"], "options": AGE_OPTIONS})
    return questions
