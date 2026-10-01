"""
MedAssist AI — FastAPI application.

Run:   python run.py            (or)   uvicorn backend.main:app --reload
Docs:  http://127.0.0.1:8000/docs   (interactive Swagger UI for every endpoint)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import graph_neo4j, llm
from .db import DEFAULT_PATH, Store
from .matching import WEIGHTS
from .pipeline import MedAssistEngine

app = FastAPI(
    title="MedAssist AI API",
    version="0.4.0",
    description="Team Neuraxis — multilingual AI symptom triage with ConText NLP, a medical knowledge graph, "
                "information-gain clarifying questions and explainable doctor matching. "
                "Global Innoventure Hackathon 2026, Problem Statement 5.",
)
# Open CORS so other teams' systems can call this API during common-problem integration.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

store = Store(DEFAULT_PATH)
engine = MedAssistEngine(store=store)
graph_status = graph_neo4j.connect_if_configured(engine)   # optional Neo4j; in-memory otherwise


class Slots(BaseModel):
    duration_days: float | None = Field(None, ge=0, le=3650)
    severity: str | None = Field(None, pattern="^(mild|normal|severe)$")
    age: int | None = Field(None, ge=0, le=120)


class AnalyzeRequest(BaseModel):
    text: str = Field("", max_length=1000, examples=["mujhe 3 din se tez bukhar hai aur badan dard"])
    lat: float = Field(28.5440, ge=-90, le=90)
    lon: float = Field(77.3330, ge=-180, le=180)
    age: int | None = Field(None, ge=0, le=120)
    mode: str = Field("in_person", pattern="^(in_person|video)$")
    answers: dict[str, bool] = Field(default_factory=dict, description="Answers to clarifying questions: {symptom_id: yes/no}")
    slots: Slots = Field(default_factory=Slots, description="Answers to detail questions (duration, severity, age)")
    extra_symptoms: list[str] = Field(default_factory=list, description="v1 field: symptom IDs treated as 'yes' answers")


class BookRequest(BaseModel):
    doctor_id: str
    slot: str = Field(..., examples=["2026-10-02T10:20"])
    patient_name: str = Field("Patient", max_length=80)
    mode: str = Field("in_person", pattern="^(in_person|video)$")


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok", "time": datetime.now().isoformat(timespec="seconds"),
            "knowledge_graph": engine.kg.stats(), "graph_backend": graph_status,
            "doctors": len(engine.doctors), "llm": llm.config_summary()}


@app.get("/api/meta", tags=["system"])
def meta():
    """Everything the UI needs at start-up: symptom catalogue, preset locations, matching weights."""
    return {
        "symptoms": [{"id": s, "en": v["label"]["en"], "hi": v["label"]["hi"]} for s, v in engine.kg.symptoms.items()],
        "locations": engine.locations, "weights": WEIGHTS, "kg": engine.kg.stats(), "llm": llm.config_summary(),
        "graph_backend": graph_status,
    }


@app.post("/api/analyze", tags=["triage"])
def analyze(req: AnalyzeRequest):
    """Full pipeline: language → NLP + ConText → knowledge graph → risk → triage → doctors → next questions."""
    if not req.text.strip() and not req.extra_symptoms and not req.answers:
        raise HTTPException(400, "Please describe your symptoms.")
    slots = {k: v for k, v in req.slots.model_dump().items() if v is not None}
    return engine.analyze(req.text, req.lat, req.lon, req.age, req.mode, req.extra_symptoms,
                          answers=req.answers, slots=slots)


@app.get("/api/doctors", tags=["doctors"])
def doctors():
    return engine.doctors


@app.get("/api/doctors/{doctor_id}/slots", tags=["doctors"])
def slots(doctor_id: str):
    d = engine.doctor_by_id.get(doctor_id)
    if not d:
        raise HTTPException(404, "Doctor not found")
    return [s.isoformat(timespec="minutes") for s in engine.scheduler.free_slots(d, datetime.now(), limit=24)]


@app.post("/api/book", tags=["booking"])
def book(req: BookRequest):
    d = engine.doctor_by_id.get(req.doctor_id)
    if not d:
        raise HTTPException(404, "Doctor not found")
    try:
        return engine.scheduler.book(d, req.slot, req.patient_name, req.mode)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/bookings", tags=["booking"])
def bookings():
    return list(engine.scheduler.bookings.values())


@app.get("/api/insights", tags=["public health"])
def insights(days: int = 14):
    """Anonymised case statistics and outbreak alerts for health officers."""
    data = store.insights(days=max(3, min(days, 60)))
    names = lambda cid: engine.kg.conditions.get(cid, {}).get("name", {"en": cid, "hi": cid})
    for a in data["alerts"]:
        a["name"] = names(a["condition"])
    data["top_conditions"] = [{"id": c, "name": names(c), "cases": n} for c, n in data["top_conditions"]]
    data["top_symptoms"] = [{"id": s, "en": engine.kg.label(s, "en"), "hi": engine.kg.label(s, "hi"), "cases": n}
                            for s, n in data["top_symptoms"]]
    data["areas"] = [{**a, "top": [{"id": c, "name": names(c), "cases": n} for c, n in a["top"]]} for a in data["areas"]]
    return data


@app.post("/api/insights/demo-data", tags=["public health"])
def seed_demo():
    """Add clearly-flagged SIMULATED cases (incl. a dengue cluster in Dadri) for demonstrations."""
    return {"added": store.seed_demo(engine)}


@app.delete("/api/insights/demo-data", tags=["public health"])
def clear_demo():
    return {"removed": store.clear_demo()}


@app.get("/api/knowledge-graph", tags=["knowledge graph"])
def knowledge_graph():
    """Conditions with ICD-10 codes, specialties, symptom edges and source links."""
    kg = engine.kg
    return {
        "stats": kg.stats(), "backend": graph_status,
        "conditions": [{"id": cid, "name": c["name"], "icd10": c.get("icd10"), "specialty": c["specialty"],
                        "severity": c["severity"], "info_source": c.get("info_source"),
                        "symptoms": [{"id": s, "en": kg.label(s), "weight": w} for s, w in c["symptoms"].items()]}
                       for cid, c in kg.conditions.items()],
        "red_flags": [{"id": r["id"], "message": r["message"]["en"]} for r in kg.red_flag_rules],
    }


@app.get("/api/knowledge-graph/cypher", tags=["knowledge graph"], response_class=PlainTextResponse)
def cypher():
    """Export the medical knowledge graph as Neo4j Cypher."""
    return engine.kg.to_cypher()


# Front-end (served last so /api and /docs take priority).
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
