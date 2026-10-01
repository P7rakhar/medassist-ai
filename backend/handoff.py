"""
Doctor handoff: turns one analysis into a structured pre-consultation note.

The note travels with a booking, so the doctor sees the patient's symptoms, what they said
they do NOT have, how long and how bad, existing conditions, the triage level and its
reasons, and the patient's own words, before the consultation starts. A plain-text version
(English or Hindi) is used for "Send on WhatsApp" and for printing.

Everything here is patient-reported and AI-structured; the note says so on every copy.
"""
from __future__ import annotations

from datetime import datetime

from .nlp import SYMPTOM_PARENTS

LEVEL = {
    "en": {"LOW": "LOW risk", "MODERATE": "MODERATE risk", "HIGH": "HIGH risk", "UNCERTAIN": "UNCERTAIN, needs a doctor's review"},
    "hi": {"LOW": "कम जोखिम", "MODERATE": "मध्यम जोखिम", "HIGH": "उच्च जोखिम", "UNCERTAIN": "अस्पष्ट, डॉक्टर की समीक्षा ज़रूरी"},
}
SEVERITY = {"en": {"severe": "severe", "mild": "mild"}, "hi": {"severe": "गंभीर", "mild": "हल्का"}}
NOTICE = {
    "en": "Patient-reported, AI-structured summary. Not a diagnosis.",
    "hi": "मरीज़ द्वारा बताया गया, AI द्वारा व्यवस्थित सारांश। यह निदान नहीं है।",
}
HEAD = {
    "en": {"title": "MedAssist AI: symptom summary for the doctor", "triage": "Triage", "symptoms": "Symptoms",
           "possible": "(possible)", "denied": "Says NO to", "past": "In the past only", "risk": "Existing conditions",
           "family": "Family history", "details": "Details", "duration": "duration", "days": "days", "hours": "hours",
           "severity": "severity", "temp": "temperature", "age": "age", "pain": "pain", "answers": "Answers to follow-up questions",
           "yes": "yes", "no": "no", "causes": "Possible causes to consider", "specialty": "Suggested specialty",
           "words": "Patient's own words", "asked": "(asked)", "generated": "Generated", "emergency": "EMERGENCY: call 112 / 108 now",
           "action": "Advice given"},
    "hi": {"title": "MedAssist AI: डॉक्टर के लिए लक्षणों का सारांश", "triage": "ट्राइएज", "symptoms": "लक्षण",
           "possible": "(शायद)", "denied": "इनसे मना किया", "past": "सिर्फ़ पहले था", "risk": "पहले से बीमारी",
           "family": "परिवार में", "details": "विवरण", "duration": "अवधि", "days": "दिन", "hours": "घंटे",
           "severity": "गंभीरता", "temp": "तापमान", "age": "उम्र", "pain": "दर्द", "answers": "सवालों के जवाब",
           "yes": "हां", "no": "नहीं", "causes": "संभावित कारण", "specialty": "सुझाई गई विशेषज्ञता",
           "words": "मरीज़ के अपने शब्द", "asked": "(पूछा गया)", "generated": "बनाया गया", "emergency": "आपातकाल: अभी 112 / 108 पर कॉल करें",
           "action": "दी गई सलाह"},
}


def _lab(x: dict, lang: str) -> str:
    return x.get(lang) or x.get("en") or x.get("id", "")


def build_note(result: dict, text: str, now: datetime | None = None) -> dict:
    """Structured note from an analyze() result and the patient's original text."""
    now = now or datetime.now()
    tr = result["triage"]
    ids = {s["id"] for s in result["symptoms"]}
    implied = {SYMPTOM_PARENTS[i] for i in ids if i in SYMPTOM_PARENTS}     # "High fever" already says "fever"
    asked = set(result.get("answers") or {})                               # answered a follow-up question
    note = {
        "generated_at": now.isoformat(timespec="minutes"),
        "notice": NOTICE,
        "language": result["language"]["name"],
        "patient_words": text,
        "triage": {"level": tr["level"], "score": tr["score"], "emergency": tr["emergency"],
                   "reasons": [{"en": r["en"], "hi": r["hi"]} for r in tr["reasons"]], "action": tr["action"]},
        "symptoms": [{"id": s["id"], "en": s["en"], "hi": s["hi"], "possible": s["uncertain"], "asked": s["id"] in asked}
                     for s in result["symptoms"] if s["id"] not in implied],
        "denied": [{"id": s["id"], "en": s["en"], "hi": s["hi"], "asked": s["id"] in asked} for s in result["negated"]],
        "past": [{"id": s["id"], "en": s["en"], "hi": s["hi"]} for s in result["historical"]],
        "risk_factors": [r["label"] for r in result["risk_factors"]],
        "family_history": [{"en": f.get("en", f["id"]), "hi": f.get("hi", f["id"])} for f in result["family_history"]],
        "details": {k: result.get(k) for k in ("duration_days", "severity", "temperature_f", "age", "pain_score")},
        "possible_conditions": [{"en": c["name"]["en"], "hi": c["name"]["hi"], "icd10": c["icd10"],
                                 "likelihood": c["likelihood"]} for c in result["conditions"]],
        "specialty": result["specialty"],
    }
    note["text"] = {"en": to_text(note, "en"), "hi": to_text(note, "hi")}
    return note


def _duration(d: float, h: dict) -> str:
    return f"{round(d * 24)} {h['hours']}" if d < 1 else f"{d:g} {h['days']}"


def to_text(note: dict, lang: str = "en") -> str:
    """Plain text for WhatsApp / printing (WhatsApp shows *text* in bold)."""
    h = HEAD[lang]
    tr = note["triage"]
    lines = [f"*{h['title']}*", f"_{note['notice'][lang]}_", ""]
    if tr["emergency"]:
        lines.append(f"*⚠ {h['emergency']}*")
    score = f" ({tr['score']}/100)" if tr["score"] is not None else ""
    lines.append(f"*{h['triage']}:* {LEVEL[lang][tr['level']]}{score}")
    lines.append(f"{h['action']}: {tr['action'][lang]}")
    if note["symptoms"]:
        lines.append(f"*{h['symptoms']}:* " + ", ".join(_lab(s, lang) + (f" {h['possible']}" if s["possible"] else "")
                                                    + (f" {h['asked']}" if s["asked"] else "") for s in note["symptoms"]))
    if note["denied"]:
        lines.append(f"*{h['denied']}:* " + ", ".join(_lab(s, lang) + (f" {h['asked']}" if s["asked"] else "")
                                                   for s in note["denied"]))
    if note["past"]:
        lines.append(f"{h['past']}: " + ", ".join(_lab(s, lang) for s in note["past"]))
    if note["risk_factors"]:
        lines.append(f"{h['risk']}: " + ", ".join(_lab(r, lang) for r in note["risk_factors"]))
    if note["family_history"]:
        lines.append(f"{h['family']}: " + ", ".join(_lab(r, lang) for r in note["family_history"]))
    d = note["details"]
    bits = []
    if d["duration_days"] is not None:
        bits.append(f"{h['duration']} {_duration(d['duration_days'], h)}")
    if d["severity"] in SEVERITY[lang]:
        bits.append(f"{h['severity']} {SEVERITY[lang][d['severity']]}")
    if d["temperature_f"] is not None:
        bits.append(f"{h['temp']} {d['temperature_f']}°F")
    if d["age"] is not None:
        bits.append(f"{h['age']} {d['age']}")
    if d["pain_score"] is not None:
        bits.append(f"{h['pain']} {d['pain_score']}/10")
    if bits:
        lines.append(f"{h['details']}: " + " · ".join(bits))
    if note["possible_conditions"]:
        lines.append(f"{h['causes']}: " + ", ".join(f"{_lab(c, lang)}" + (f" ({c['icd10']})" if c["icd10"] else "")
                                                   for c in note["possible_conditions"]))
    lines.append(f"{h['specialty']}: {_lab(note['specialty'], lang)}")
    if note["patient_words"]:
        lines.append(f"{h['words']}: “{note['patient_words']}”")
    lines.append(f"{h['generated']}: {note['generated_at'].replace('T', ' ')}")
    return "\n".join(lines)
