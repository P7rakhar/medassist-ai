"""
The 7-step AI symptom analysis pipeline from slide 5:

  1 User input -> 2 Language detection -> 3 NLP tokenisation -> 4 Entity extraction
  -> 5 Knowledge-graph query -> 6 Risk scoring -> 7 Triage & recommendation
  (+ clarifying questions for the next round)

Each step is timed and returned in `trace`, so the UI (and the judges) can see
exactly how a result was produced.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from . import llm
from .clarify import next_questions
from .handoff import build_note
from .knowledge_graph import KnowledgeGraph
from .matching import rank_doctors
from .model import SecondOpinion
from .nlp import Mention, SymptomExtractor, detect_language, normalise
from .scheduler import SlotScheduler
from .triage import assess

DATA = Path(__file__).parent / "data"

DISCLAIMER = {
    "en": "MedAssist AI gives triage guidance, not a diagnosis. Always consult a qualified doctor. In an emergency call 112 / 108.",
    "hi": "MedAssist AI केवल मार्गदर्शन देता है, निदान नहीं। हमेशा योग्य डॉक्टर से सलाह लें। आपातकाल में 112 / 108 पर कॉल करें।",
}
SEVERITY_VALUES = {"mild", "normal", "severe"}


class MedAssistEngine:
    def __init__(self, data_dir: Path = DATA, store=None):
        self.kg = KnowledgeGraph(data_dir / "knowledge_graph.json")
        self.extractor = SymptomExtractor(self.kg.symptoms, data_dir / "context_triggers.json",
                                          risk_factors=self.kg.risk_factors,
                                          condition_names=self.kg.mentioned_conditions)
        doc_data = json.loads((data_dir / "doctors.json").read_text(encoding="utf-8"))
        self.doctors: list[dict] = doc_data["doctors"]
        self.locations: list[dict] = doc_data["locations"]
        self.doctor_by_id = {d["id"]: d for d in self.doctors}
        self.store = store                      # optional SQLite store (db.py): case log + bookings
        self.scheduler = SlotScheduler(store=store)
        self.graph_backend = "in-memory"
        self.second = SecondOpinion()            # trained model (training/train_model.py); optional

    def nearest_area(self, lat: float, lon: float) -> str:
        from .matching import haversine_km
        best = min(self.locations, key=lambda l: haversine_km(lat, lon, l["lat"], l["lon"]))
        return best["name"] if haversine_km(lat, lon, best["lat"], best["lon"]) <= 15 else "Other area"

    def analyze(self, text: str, lat: float, lon: float, age: int | None = None,
                mode: str = "in_person", extra_symptoms: list[str] | None = None,
                now: datetime | None = None, answers: dict[str, bool] | None = None,
                slots: dict | None = None, log_case: bool = True) -> dict:
        now = now or datetime.now()
        answers = dict(answers or {})
        for sid in extra_symptoms or []:          # v1 clients: "extra_symptoms" means "yes" answers
            answers.setdefault(sid, True)
        slots = slots or {}
        trace: list[dict] = []
        t_all = time.perf_counter()

        def step(n: int, name: str, t0: float, output):
            trace.append({"step": n, "name": name, "ms": round((time.perf_counter() - t0) * 1000, 2), "output": output})

        # 1. Input
        t0 = time.perf_counter()
        text = (text or "").strip()[:1000]
        step(1, "User input (voice / text)", t0, {"chars": len(text), "text": text,
                                                  "answers": len(answers), "slots": sorted(slots)})

        # 2. Language detection
        t0 = time.perf_counter()
        lang = detect_language(text)
        step(2, "Language detection", t0, lang)

        # 3. Tokenisation
        t0 = time.perf_counter()
        tokens = normalise(text).split()
        step(3, "NLP normalisation & tokenisation", t0, {"tokens": tokens[:40], "count": len(tokens)})

        # 4. Entity extraction (lexicon + body-part composer + ConText)
        t0 = time.perf_counter()
        ext = self.extractor.extract(text, now)
        for sid, yes in answers.items():
            if sid in self.kg.symptoms:
                ext.mentions.append(Mention(sid, "(answered yes)" if yes else "(answered no)", negated=not yes, method="answer"))
        llm_note = None
        if not ext.present and text and (llm.enabled() or lang["code"] not in ("en", "hi", "hinglish")):
            ids, llm_note = llm.extract_symptom_ids(text, {s: self.kg.label(s) for s in self.kg.symptoms})
            for sid in ids:
                ext.mentions.append(Mention(sid, "(LLM)", method="llm"))
        duration = slots.get("duration_days", ext.duration_days)
        severity = slots.get("severity") if slots.get("severity") in SEVERITY_VALUES else ext.severity
        age = age if age is not None else slots.get("age", ext.age)
        weights, present, absent = ext.weights, ext.present, ext.absent
        risk_factors = [{"id": r["id"], "label": self.kg.risk_factors[r["id"]]["label"],
                         "points": self.kg.risk_factors[r["id"]]["points"]} for r in ext.risk_factors]
        step(4, "Medical entity extraction", t0, {
            "symptoms": present, "uncertain": ext.uncertain, "negated": absent, "historical": ext.historical,
            "family_history": ext.family_history, "risk_factors": [r["id"] for r in risk_factors],
            "conditions_named": ext.condition_mentions, "context_triggers": ext.triggers,
            "duration_days": duration, "severity": severity, "pain_score": ext.pain_score,
            "temperature_f": ext.temperature_f, "spo2": ext.spo2, "age": age, "not_understood": ext.unrecognised,
            "methods": sorted({m.method for m in ext.mentions}), "llm": llm_note,
        })

        # 5. Knowledge graph query
        t0 = time.perf_counter()
        all_candidates = self.kg.query(weights, absent, top_k=None)
        conditions = [c for c in all_candidates[:3] if c.raw >= 0.45 * all_candidates[0].raw] if all_candidates else []
        flags = self.kg.red_flags(present, [r["id"] for r in risk_factors])
        second = self.second.predict(text, weights, [c.id for c in conditions]) if present else None
        if second and second.get("available"):
            for t in second["top"]:
                kg_name = self.kg.conditions.get(t["kg_id"], {}).get("name") if t["kg_id"] else None
                nice = t["label"][0].upper() + t["label"][1:]
                t["name"] = {"en": kg_name["en"] if kg_name else nice, "hi": kg_name["hi"] if kg_name else nice}
        step(5, "Knowledge graph query", t0, {
            "second_opinion": [f"{t['label']} {round(t['probability'] * 100)}%" for t in second["top"]]
                              if second and second.get("available") else [],
            "candidates_scored": len(all_candidates),
            "candidates": [{"id": c.id, "likelihood": c.likelihood, "coverage": c.coverage} for c in conditions],
            "red_flags": [f["id"] for f in flags],
        })

        # 6. Risk scoring
        t0 = time.perf_counter()
        triage = assess(present, conditions, flags, duration, severity, age, ext.temperature_f, risk_factors, ext.spo2)
        step(6, "Risk scoring", t0, {"level": triage["level"], "score": triage["score"]})

        # 7. Triage & recommendation (doctor matching)
        t0 = time.perf_counter()
        uncertain_case = triage["level"] == "UNCERTAIN"
        # UNCERTAIN -> escalate to a human general physician rather than guessing a specialist.
        match_weights = weights or {"fever": 1.0, "headache": 1.0, "fatigue": 1.0}
        doctors = rank_doctors(self.kg, self.scheduler, self.doctors, match_weights, lat, lon,
                               lang["code"], mode=mode, now=now, emergency=triage["emergency"],
                               only_specialty="General Physician" if uncertain_case else None,
                               allow_emergency_dept=triage["level"] == "HIGH")
        top_specialty = conditions[0].specialty if conditions and not uncertain_case else "General Physician"
        step(7, "Triage & doctor recommendation", t0, {"specialty": top_specialty, "doctors": [d["id"] for d in doctors]})

        # 8. Clarifying questions for the next round
        t0 = time.perf_counter()
        questions = [] if triage["emergency"] else next_questions(
            self.kg, weights, absent, set(answers), duration, severity, ext.pain_score, age,
            ext.unplaced_sensations if not present else [], triage["level"], set(slots))
        step(8, "Clarifying questions (safety + information gain)", t0,
             {"questions": [q.get("id") or q.get("slot") or q["type"] for q in questions]})

        lab = lambda sid: {"id": sid, "en": self.kg.label(sid, "en"), "hi": self.kg.label(sid, "hi")}
        cond_label = lambda cid: self.kg.conditions[cid]["name"] if cid in self.kg.conditions else {"en": cid, "hi": cid}
        result = {
            "language": lang,
            "symptoms": [{**lab(m.symptom_id), "matched_text": m.text, "method": m.method,
                          "uncertain": weights.get(m.symptom_id, 1.0) < 1.0}
                         for m in _first_active(ext.mentions)],
            "negated": [lab(s) for s in absent],
            "historical": [lab(s) for s in ext.historical],
            "risk_factors": risk_factors,
            "family_history": [{"id": r, **(self.kg.risk_factors.get(r, {}).get("label") or cond_label(r))} for r in ext.family_history],
            "conditions_named": [{**c, "name": cond_label(c["id"])} for c in ext.condition_mentions],
            "not_understood": ext.unrecognised,
            "duration_days": duration, "severity": severity, "pain_score": ext.pain_score,
            "temperature_f": ext.temperature_f, "spo2": ext.spo2, "age": age,
            "conditions": [{"id": c.id, "name": c.name, "specialty": c.specialty,
                            "specialty_hi": self.kg.specialties[c.specialty]["hi"],
                            "likelihood": c.likelihood, "coverage": c.coverage, "icd10": c.icd10,
                            "info_source": c.info_source,
                            "matched": [lab(s) for s in c.matched], "advice": c.advice} for c in conditions],
            "triage": triage,
            "specialty": {"en": top_specialty, "hi": self.kg.specialties[top_specialty]["hi"]},
            "second_opinion": second if second and second.get("available") else None,
            "questions": questions,
            "follow_up": [q["label"] | {"id": q["id"]} for q in questions if q["type"] == "symptom"],  # v1 field
            "answers": answers, "slots": slots,
            "doctors": doctors, "mode": mode,
            "trace": trace, "total_ms": round((time.perf_counter() - t_all) * 1000, 2),
            "disclaimer": DISCLAIMER,
        }
        # Pre-consultation note for the doctor (also used for WhatsApp sharing and printing).
        result["handoff"] = build_note(result, text, now)
        if self.store and log_case and (present or text):
            self.store.log_case(now, self.nearest_area(lat, lon), lat, lon, lang["code"], triage["level"],
                                triage["score"], conditions[0].id if conditions else None, present)
        return result


def _first_active(mentions: list[Mention]) -> list[Mention]:
    seen, out = set(), []
    for m in mentions:
        if m.active and m.symptom_id not in seen:
            seen.add(m.symptom_id)
            out.append(m)
    return out
