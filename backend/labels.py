"""
Doctor-labelled cases.

When a doctor sees a patient who booked through MedAssist, they record their own triage level
(and optionally the diagnosis) in the doctor view. Each such booking becomes a labelled case:
the patient's own words and the AI's assessment, paired with the doctor's judgement.

This is how the evaluation grows from real use instead of team-written cases:
  GET /api/labelled-cases            -> the cases + agreement statistics (no patient names)
  python tests/run_eval.py --db medassist.db   -> re-runs the current engine on them
"""
from __future__ import annotations

from collections import Counter

LEVELS = ("LOW", "MODERATE", "HIGH")
RANK = {lv: i for i, lv in enumerate(LEVELS)}


def labelled_cases(bookings: list[dict]) -> list[dict]:
    out = []
    for b in bookings:
        note = b.get("note")
        if not note or not b.get("doctor_level"):
            continue
        tr = note["triage"]
        out.append({
            "case_id": b["booking_id"], "reviewed_at": b.get("reviewed_at"), "language": note.get("language"),
            "patient_words": note.get("patient_words", ""),
            "symptoms": [s["id"] for s in note.get("symptoms", [])], "denied": [s["id"] for s in note.get("denied", [])],
            "ai_level": tr["level"], "ai_score": tr.get("score"),
            "ai_conditions": [c["en"] for c in note.get("possible_conditions", [])],
            "doctor_level": b["doctor_level"], "doctor_condition": b.get("doctor_condition"),
            "doctor_comment": b.get("doctor_comment"),
        })
    return sorted(out, key=lambda c: c["reviewed_at"] or "", reverse=True)


def agreement(cases: list[dict], level_key: str = "ai_level") -> dict:
    """How often the AI's level matched the doctor's, and in which direction it was wrong."""
    n = len(cases)
    matrix = Counter((c[level_key], c["doctor_level"]) for c in cases)
    agree = sum(c[level_key] == c["doctor_level"] for c in cases)
    rated = [c for c in cases if c[level_key] in RANK]
    under = sum(RANK[c[level_key]] < RANK[c["doctor_level"]] for c in rated)
    over = sum(RANK[c[level_key]] > RANK[c["doctor_level"]] for c in rated)
    return {"cases": n, "agree": agree, "agreement": round(agree / n, 3) if n else None,
            "ai_lower_than_doctor": under, "ai_higher_than_doctor": over,
            "ai_uncertain": sum(c[level_key] == "UNCERTAIN" for c in cases),
            "matrix": [{"ai": a, "doctor": d, "cases": k} for (a, d), k in sorted(matrix.items())]}
