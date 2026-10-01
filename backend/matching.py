"""
Smart doctor matching (slide 5).

Match Score = w1*Speciality_Match + w2*Distance_Score + w3*Rating
            + w4*Availability + w5*Language_Match + w6*Cost_Factor
with w1=0.30, w2=0.20, w3=0.15, w4=0.15, w5=0.10, w6=0.10   (sum = 1.0)

Every component is scaled to 0..1, so the final score is 0..1 as well.
"""
from __future__ import annotations

import math
from datetime import datetime

from .knowledge_graph import KnowledgeGraph
from .scheduler import SlotScheduler

WEIGHTS = {"specialty": 0.30, "distance": 0.20, "rating": 0.15,
           "availability": 0.15, "language": 0.10, "cost": 0.10}

EARTH_RADIUS_KM = 6371.0
DISTANCE_SCALE_KM = 5.0       # score halves at 5 km
AVAILABILITY_SCALE_H = 12.0   # score halves if the next free slot is 12 h away
RATING_PRIOR, RATING_PRIOR_WEIGHT = 3.5, 10
MAX_FEE = 1500.0
MAX_DISTANCE_KM = 60.0        # in-person doctors further than this are not suggested
MIN_SPECIALTY_MATCH = 0.20    # a nearby, cheap doctor of an unrelated specialty is never suggested


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two GPS points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def distance_score(km: float) -> float:
    """Inverse-distance weighting: 1 at 0 km, 0.5 at 5 km, 0.2 at 20 km."""
    return 1.0 / (1.0 + km / DISTANCE_SCALE_KM)


def bayesian_rating(rating: float, reviews: int) -> float:
    """Shrink ratings with few reviews toward the prior (3.5), so 5.0 from 2 reviews < 4.6 from 300."""
    return (RATING_PRIOR_WEIGHT * RATING_PRIOR + reviews * rating) / (RATING_PRIOR_WEIGHT + reviews)


def availability_score(hours_until_slot: float | None) -> float:
    if hours_until_slot is None:
        return 0.0
    return 1.0 / (1.0 + max(0.0, hours_until_slot) / AVAILABILITY_SCALE_H)


def language_score(patient_lang: str, doctor_langs: list[str]) -> float:
    lang = "hi" if patient_lang == "hinglish" else patient_lang
    if lang in doctor_langs:
        return 1.0
    return 0.3 if "en" in doctor_langs and lang != "en" else 0.0


def cost_score(fee: float) -> float:
    return 1.0 - min(fee, MAX_FEE) / MAX_FEE


def patient_vector(present: list[str] | dict[str, float]) -> dict[str, float]:
    """Symptom vector: 1.0 per symptom, or the certainty weight (0.5 for 'maybe') when given a dict."""
    return dict(present) if isinstance(present, dict) else {s: 1.0 for s in present}


def rank_doctors(kg: KnowledgeGraph, scheduler: SlotScheduler, doctors: list[dict], present: list[str] | dict[str, float],
                 lat: float, lon: float, patient_lang: str, mode: str = "in_person",
                 now: datetime | None = None, top_k: int = 5, emergency: bool = False,
                 only_specialty: str | None = None, allow_emergency_dept: bool = True) -> list[dict]:
    """mode: 'in_person' (distance matters) or 'video' (teleconsult; distance is irrelevant)."""
    now = now or datetime.now()
    pvec = patient_vector(present)
    ranked = []
    for d in doctors:
        if only_specialty and d["specialty"] != only_specialty:
            continue
        if d["specialty"] == "Emergency Medicine" and not allow_emergency_dept:
            continue  # don't send low/moderate-risk patients to an emergency department
        if mode == "video" and not d.get("teleconsult"):
            continue
        if mode == "in_person" and d.get("tele_only"):
            continue
        km = haversine_km(lat, lon, d["lat"], d["lon"])
        if mode == "in_person" and km > MAX_DISTANCE_KM:
            continue
        next_slot = scheduler.next_slot(d, now)
        hours = (next_slot - now).total_seconds() / 3600 if next_slot else None
        comp = {
            "specialty": kg.specialty_match(pvec, d["specialty"]) if pvec else 0.0,
            "distance": 1.0 if mode == "video" else distance_score(km),
            "rating": bayesian_rating(d["rating"], d["reviews"]) / 5.0,
            "availability": availability_score(hours),
            "language": language_score(patient_lang, d["languages"]),
            "cost": cost_score(d["fee"]),
        }
        if comp["specialty"] < MIN_SPECIALTY_MATCH and not (emergency and d.get("emergency")):
            continue
        score = sum(WEIGHTS[k] * v for k, v in comp.items())
        ranked.append({
            "id": d["id"], "name": d["name"], "specialty": d["specialty"],
            "specialty_hi": kg.specialties[d["specialty"]]["hi"],
            "clinic": d["clinic"], "area": d["area"], "fee": d["fee"], "languages": d["languages"],
            "rating": d["rating"], "reviews": d["reviews"], "teleconsult": d.get("teleconsult", False),
            "emergency": d.get("emergency", False), "tele_only": d.get("tele_only", False),
            "distance_km": None if d.get("tele_only") else round(km, 1),
            "bayesian_rating": round(bayesian_rating(d["rating"], d["reviews"]), 2),
            "next_slot": next_slot.isoformat(timespec="minutes") if next_slot else None,
            "hours_until_slot": round(hours, 1) if hours is not None else None,
            "slots": [s.isoformat(timespec="minutes") for s in scheduler.free_slots(d, now, limit=6)],
            "components": {k: round(v, 3) for k, v in comp.items()},
            "contributions": {k: round(WEIGHTS[k] * v, 3) for k, v in comp.items()},
            "match_score": round(score, 3),
        })
    ranked.sort(key=lambda r: -r["match_score"])
    if emergency and mode == "in_person":
        # Safety rule: in an emergency, the nearest 24x7 emergency-capable facility is always shown first.
        er = sorted((r for r in ranked if r["emergency"]), key=lambda r: r["distance_km"] or 0)
        if er:
            ranked.remove(er[0])
            ranked.insert(0, {**er[0], "pinned_reason": "Nearest 24×7 emergency facility"})
    return ranked[:top_k]
