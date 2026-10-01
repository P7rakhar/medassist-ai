"""
Risk scoring and triage classification (slide 5: LOW / MODERATE / HIGH / UNCERTAIN).

Order of decisions:
  1. No recognisable symptoms                -> UNCERTAIN (escalate to a human doctor)
  2. Any red-flag rule fires                 -> HIGH (hard safety override, never averaged away)
  3. Symptoms that fit no clear pattern      -> UNCERTAIN
  4. Otherwise a 0-100 risk score            -> LOW (<35) / MODERATE (35-64) / HIGH (>=65)
     with a floor: chest pain, breathlessness or blood in urine are never LOW
"""
from __future__ import annotations

from .knowledge_graph import ConditionMatch

LOW_MAX, MODERATE_MAX = 35, 65

ACTIONS = {
    "LOW": {"en": "Self-care at home. Book a routine consultation if you are not better in 3 days.",
            "hi": "घर पर देखभाल करें। 3 दिन में आराम न मिले तो सामान्य परामर्श बुक करें।"},
    "MODERATE": {"en": "Book a doctor's appointment within 48 hours.",
                 "hi": "48 घंटे के भीतर डॉक्टर से अपॉइंटमेंट लें।"},
    "HIGH": {"en": "Seek care now: start a video consultation or go to the nearest emergency department. Call 108 / 112 if it is severe.",
             "hi": "अभी इलाज लें: वीडियो परामर्श शुरू करें या नज़दीकी इमरजेंसी जाएं। गंभीर हो तो 108 / 112 पर कॉल करें।"},
    "UNCERTAIN": {"en": "We could not assess this confidently. Your case is flagged for review by a human doctor — please describe your symptoms in more detail or consult a general physician.",
                  "hi": "हम इसका भरोसेमंद आकलन नहीं कर सके। आपका मामला डॉक्टर की समीक्षा के लिए भेजा गया है — लक्षण विस्तार से बताएं या सामान्य चिकित्सक से मिलें।"},
}


def severity_points(sev: float) -> float:
    """Map condition severity 1..3 onto 15..80 risk points."""
    return 15 + (max(1.0, min(3.0, sev)) - 1.0) * 32.5


MAX_RISK_FACTOR_POINTS = 15

# Symptoms that are never rated LOW, however benign the rest looks
# (a heart attack can feel like acidity; breathlessness or blood in urine always needs a doctor).
NEVER_LOW = {
    "chest_pain": ("Chest pain is never rated low risk: heart problems can feel like acidity",
                   "सीने के दर्द को कभी कम जोखिम नहीं माना जाता: दिल की समस्या एसिडिटी जैसी लग सकती है"),
    "breathlessness": ("Breathlessness is never rated low risk", "सांस फूलने को कभी कम जोखिम नहीं माना जाता"),
    "blood_in_urine": ("Blood in urine is never rated low risk", "पेशाब में खून को कभी कम जोखिम नहीं माना जाता"),
}


def assess(present: list[str], conditions: list[ConditionMatch], red_flags: list[dict],
           duration_days: float | None, severity: str, age: int | None,
           temperature_f: float | None = None, risk_factors: list[dict] | None = None) -> dict:
    """risk_factors: [{"id", "label": {"en","hi"}, "points"}] for existing conditions such as diabetes or pregnancy."""
    reasons: list[dict] = []

    def add(en: str, hi: str, points: float = 0):
        reasons.append({"en": en, "hi": hi, "points": round(points, 1)})

    if not present:
        add("No symptoms could be identified from the description.", "विवरण से कोई लक्षण पहचाना नहीं जा सका।")
        return _result("UNCERTAIN", None, reasons, confidence=0.0)

    if red_flags:
        for rf in red_flags:
            add(rf["message"]["en"], rf["message"]["hi"])
        return _result("HIGH", 95, reasons, confidence=1.0, emergency=True)

    top = conditions[0] if conditions else None
    if top is None or (top.coverage < 0.2 and len(present) >= 3):
        add("These symptoms do not fit a clear pattern in our knowledge graph.",
            "ये लक्षण हमारे नॉलेज ग्राफ़ में किसी स्पष्ट पैटर्न से मेल नहीं खाते।")
        return _result("UNCERTAIN", None, reasons, confidence=round(top.likelihood if top else 0.0, 2))

    # Expected severity across the top candidate conditions.
    total_l = sum(c.likelihood for c in conditions) or 1.0
    base = sum(c.likelihood / total_l * severity_points(c.severity) for c in conditions)
    add(f"Base risk from likely conditions ({', '.join(c.name['en'] for c in conditions)})",
        f"संभावित स्थितियों से मूल जोखिम ({', '.join(c.name['hi'] for c in conditions)})", base)
    score = base

    if duration_days is not None and duration_days >= 7:
        score += 15; add("Symptoms for a week or more", "एक हफ्ते या उससे ज़्यादा से लक्षण", 15)
    elif duration_days is not None and duration_days >= 3:
        score += 8; add("Symptoms for 3 days or more", "3 दिन या उससे ज़्यादा से लक्षण", 8)
    if severity == "severe":
        score += 10; add("Described as severe", "गंभीर बताया गया", 10)
    elif severity == "mild":
        score -= 5; add("Described as mild", "हल्का बताया गया", -5)
    if age is not None and (age >= 60 or age < 5):
        score += 10; add(f"Higher-risk age group ({age} years)", f"अधिक जोखिम वाला आयु वर्ग ({age} वर्ष)", 10)
    if temperature_f is not None and temperature_f >= 103:
        score += 10; add(f"Very high temperature ({temperature_f}°F)", f"बहुत तेज़ बुखार ({temperature_f}°F)", 10)
    if len(present) >= 5:
        score += 5; add("Many symptoms at once", "एक साथ कई लक्षण", 5)
    rf_points = 0
    for rf in risk_factors or []:
        pts = min(rf["points"], MAX_RISK_FACTOR_POINTS - rf_points)
        if pts > 0:
            rf_points += pts; score += pts
            add(f"Existing condition: {rf['label']['en']}", f"पहले से बीमारी: {rf['label']['hi']}", pts)

    score = max(0.0, min(100.0, score))
    floor = next((sid for sid in NEVER_LOW if sid in present), None)
    if floor and score < LOW_MAX:
        add(*NEVER_LOW[floor], LOW_MAX - score); score = LOW_MAX
    level = "LOW" if score < LOW_MAX else "MODERATE" if score < MODERATE_MAX else "HIGH"
    return _result(level, round(score), reasons, confidence=round(top.likelihood, 2))


def _result(level: str, score, reasons, confidence: float, emergency: bool = False) -> dict:
    return {"level": level, "score": score, "confidence": confidence, "reasons": reasons,
            "action": ACTIONS[level], "emergency": emergency,
            "human_review": level == "UNCERTAIN",
            "thresholds": {"LOW": f"< {LOW_MAX}", "MODERATE": f"{LOW_MAX}–{MODERATE_MAX - 1}", "HIGH": f">= {MODERATE_MAX}"}}
