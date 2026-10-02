"""
FHIR R4 export of the doctor's note, shaped like ABDM's OP consultation record.

India's health-record network (ABDM) exchanges records as HL7 FHIR R4 document Bundles defined by
the NRCeS implementation guide (https://nrces.in/ndhm/fhir/r4/). This module turns one booking and
its pre-consultation note into such a Bundle:

  Bundle (type "document", profile DocumentBundle)
    Composition   profile OPConsultRecord, type SNOMED 371530004 "Clinical consultation report",
                  status "preliminary" (AI-structured, patient-reported)
      Chief complaints (SNOMED 422843007)  -> Condition per symptom; denied ones have
                                              verificationStatus "refuted", uncertain ones "provisional"
      Medical history (SNOMED 371529009)   -> past symptoms (resolved) and existing conditions
      Other observations (SNOMED 404684003)-> temperature, SpO2, pain score (LOINC-coded Observations)
      Triage (MedAssist AI)                -> RiskAssessment: triage level + possible conditions (ICD-10)
      Doctor's assessment                  -> the doctor's own triage level / diagnosis, when recorded
    Patient, Practitioner, Encounter, Device (the AI that structured the note)

What is NOT done yet, and why: ABHA numbers and facility IDs need ABDM sandbox registration, and
symptoms are sent as text (no SNOMED code mapping yet). Validation against the official FHIR
validator is the next step.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from html import escape

NRCES = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/"
SCT, LOINC, UCUM, ICD10 = "http://snomed.info/sct", "http://loinc.org", "http://unitsofmeasure.org", "http://hl7.org/fhir/sid/icd-10"
CLIN = "http://terminology.hl7.org/CodeSystem/condition-clinical"
VER = "http://terminology.hl7.org/CodeSystem/condition-ver-status"
RISK = "http://terminology.hl7.org/CodeSystem/risk-probability"
LEVEL_RISK = {"LOW": "low", "MODERATE": "moderate", "HIGH": "high", "UNCERTAIN": "moderate"}


def _id(booking_id: str, name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://medassist.ai/booking/{booking_id}/{name}"))


def _dt(value: str | datetime) -> str:
    """FHIR dateTime: a time needs a time-zone offset, so local times get the server's offset (IST on Render)."""
    d = datetime.fromisoformat(value) if isinstance(value, str) else value
    return d.astimezone().isoformat(timespec="seconds")


def _cc(system: str | None, code: str | None, display: str) -> dict:
    out = {"text": display}
    if system and code:
        out["coding"] = [{"system": system, "code": code, "display": display}]
    return out


def _div(*paras: str) -> dict:
    return {"status": "generated",
            "div": '<div xmlns="http://www.w3.org/1999/xhtml">' + "".join(f"<p>{escape(p)}</p>" for p in paras if p) + "</div>"}


def booking_bundle(booking: dict, doctor: dict, now: datetime | None = None) -> dict:
    note = booking.get("note")
    if not note:
        raise ValueError("This booking has no pre-consultation note")
    now = now or datetime.now()
    bid = booking["booking_id"]
    ref = lambda name: f"urn:uuid:{_id(bid, name)}"
    generated = _dt(note["generated_at"])
    entries: list[dict] = []

    def add(name: str, resource: dict) -> str:
        resource = {"resourceType": resource.pop("resourceType"), "id": _id(bid, name), **resource}
        entries.append({"fullUrl": ref(name), "resource": resource})
        return ref(name)

    patient = add("patient", {"resourceType": "Patient", "meta": {"profile": [NRCES + "Patient"]},
                              "name": [{"text": booking.get("patient_name") or "Patient"}]})
    practitioner = add("practitioner", {"resourceType": "Practitioner", "meta": {"profile": [NRCES + "Practitioner"]},
                                        "name": [{"text": doctor.get("name", booking.get("doctor_name", ""))}]})
    device = add("device", {"resourceType": "Device", "deviceName": [{"name": "MedAssist AI", "type": "model-name"}],
                            "version": [{"value": "0.6"}],
                            "note": [{"text": "Structures patient-reported symptoms and suggests a triage level. Not a diagnosis."}]})
    video = booking.get("mode") == "video"
    encounter = add("encounter", {
        "resourceType": "Encounter", "meta": {"profile": [NRCES + "Encounter"]},
        "status": "finished" if booking.get("status") == "seen" else "planned",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "VR" if video else "AMB",
                  "display": "virtual" if video else "ambulatory"},
        "subject": {"reference": patient},
        "participant": [{"individual": {"reference": practitioner}}],
        "period": {"start": _dt(booking["slot"]), "end": _dt(booking.get("slot_end") or booking["slot"])},
        "serviceProvider": {"display": booking.get("clinic", "")},
    })

    onset = None
    if note["details"].get("duration_days") is not None:
        onset = _dt(datetime.fromisoformat(generated) - timedelta(days=note["details"]["duration_days"]))

    def condition(name: str, label: str, clinical: str, verification: str, code=None, extra=None) -> str:
        res = {"resourceType": "Condition", "meta": {"profile": [NRCES + "Condition"]},
               "clinicalStatus": _cc(CLIN, clinical, clinical), "verificationStatus": _cc(VER, verification, verification),
               "code": _cc(*(code or (None, None)), label), "subject": {"reference": patient},
               "encounter": {"reference": encounter}, "recordedDate": generated}
        res.update(extra or {})
        return add(name, res)

    complaints = []
    for s in note["symptoms"]:
        complaints.append(condition(f"symptom-{s['id']}", s["en"], "active", "provisional" if s.get("possible") else "confirmed",
                                    extra={"onsetDateTime": onset} if onset else None))
    for s in note["denied"]:
        complaints.append(condition(f"denied-{s['id']}", s["en"], "inactive", "refuted",
                                    extra={"note": [{"text": "Patient said they do NOT have this."}]}))
    history = [condition(f"past-{s['id']}", s["en"], "resolved", "confirmed") for s in note["past"]]
    history += [condition(f"existing-{i}", r["en"], "active", "confirmed") for i, r in enumerate(note["risk_factors"])]

    observations = []
    d = note["details"]
    if d.get("temperature_f") is not None:
        observations.append(add("temperature", {
            "resourceType": "Observation", "status": "final",
            "category": [_cc("http://terminology.hl7.org/CodeSystem/observation-category", "vital-signs", "Vital Signs")],
            "code": _cc(LOINC, "8310-5", "Body temperature"), "subject": {"reference": patient}, "encounter": {"reference": encounter},
            "effectiveDateTime": generated,
            "valueQuantity": {"value": d["temperature_f"], "unit": "degF", "system": UCUM, "code": "[degF]"},
            "note": [{"text": "Reported by the patient"}]}))
    if d.get("spo2") is not None:
        observations.append(add("spo2", {
            "resourceType": "Observation", "status": "final",
            "category": [_cc("http://terminology.hl7.org/CodeSystem/observation-category", "vital-signs", "Vital Signs")],
            "code": _cc(LOINC, "59408-5", "Oxygen saturation in Arterial blood by Pulse oximetry"),
            "subject": {"reference": patient}, "encounter": {"reference": encounter}, "effectiveDateTime": generated,
            "valueQuantity": {"value": d["spo2"], "unit": "%", "system": UCUM, "code": "%"},
            "note": [{"text": "Reported by the patient"}]}))
    if d.get("pain_score") is not None:
        observations.append(add("pain", {
            "resourceType": "Observation", "status": "final",
            "code": _cc(LOINC, "72514-3", "Pain severity - 0-10 verbal numeric rating [Score] - Reported"),
            "subject": {"reference": patient}, "encounter": {"reference": encounter}, "effectiveDateTime": generated,
            "valueInteger": d["pain_score"]}))

    tr = note["triage"]
    predictions = [{"outcome": _cc(None, None, f"Triage level {tr['level']}"),
                    "qualitativeRisk": _cc(RISK, LEVEL_RISK[tr["level"]], LEVEL_RISK[tr["level"]])}]
    for c in note["possible_conditions"]:
        predictions.append({"outcome": _cc(ICD10 if c.get("icd10") else None, c.get("icd10"), c["en"]),
                            "probabilityDecimal": round(float(c["likelihood"]), 3)})
    risk = add("triage", {
        "resourceType": "RiskAssessment", "status": "preliminary", "subject": {"reference": patient},
        "encounter": {"reference": encounter}, "occurrenceDateTime": generated, "performer": {"reference": device},
        "method": _cc(None, None, "MedAssist AI: ConText NLP + medical knowledge graph + NHS-guided warning-sign rules"),
        "basis": [{"reference": r} for r in complaints[:len(note["symptoms"])]],
        "prediction": predictions,
        "mitigation": tr["action"]["en"],
        "note": [{"text": r["en"]} for r in tr["reasons"]],
    })

    review_section = None
    if booking.get("doctor_level"):
        reviewed = _dt(booking.get("reviewed_at") or now)
        review_entries = [add("doctor-triage", {
            "resourceType": "RiskAssessment", "status": "final", "subject": {"reference": patient},
            "encounter": {"reference": encounter}, "occurrenceDateTime": reviewed, "performer": {"reference": practitioner},
            "prediction": [{"outcome": _cc(None, None, f"Triage level {booking['doctor_level']}"),
                            "qualitativeRisk": _cc(RISK, LEVEL_RISK[booking["doctor_level"]], LEVEL_RISK[booking["doctor_level"]])}],
            "note": [{"text": booking["doctor_comment"]}] if booking.get("doctor_comment") else []})]
        if booking.get("doctor_condition"):
            review_entries.append(condition("doctor-diagnosis", booking["doctor_condition"], "active", "provisional",
                                            extra={"recorder": {"reference": practitioner}, "recordedDate": reviewed}))
        review_section = {"title": "Doctor's assessment", "code": _cc(SCT, "371530004", "Clinical consultation report"),
                          "text": _div(f"Doctor's triage level: {booking['doctor_level']}",
                                       f"Diagnosis: {booking.get('doctor_condition') or 'not recorded'}"),
                          "entry": [{"reference": r} for r in review_entries]}

    sections = [
        {"title": "Chief complaints", "code": _cc(SCT, "422843007", "Chief complaint section"),
         "text": _div(f"Patient's own words ({note.get('language', '')}): “{note.get('patient_words', '')}”",
                      "Symptoms: " + (", ".join(s["en"] for s in note["symptoms"]) or "none recognised"),
                      ("Says NO to: " + ", ".join(s["en"] for s in note["denied"])) if note["denied"] else ""),
         "entry": [{"reference": r} for r in complaints]},
    ]
    if history:
        sections.append({"title": "Medical history", "code": _cc(SCT, "371529009", "History and physical report"),
                         "text": _div(", ".join([s["en"] for s in note["past"]] + [r["en"] for r in note["risk_factors"]])),
                         "entry": [{"reference": r} for r in history]})
    if observations:
        sections.append({"title": "Other observations", "code": _cc(SCT, "404684003", "Clinical finding"),
                         "text": _div("Values reported by the patient"), "entry": [{"reference": r} for r in observations]})
    sections.append({"title": "Triage (MedAssist AI)", "code": _cc(SCT, "225390008", "Triage"),
                     "text": _div(f"Triage level: {tr['level']}" + (f" ({tr['score']}/100)" if tr.get("score") is not None else ""),
                                  "Advice given: " + tr["action"]["en"], note["notice"]["en"]),
                     "entry": [{"reference": risk}]})
    if review_section:
        sections.append(review_section)

    composition = {
        "resourceType": "Composition", "id": _id(bid, "composition"),
        "meta": {"profile": [NRCES + "OPConsultRecord"]}, "language": "en-IN",
        "identifier": {"system": "https://medassist.ai/notes", "value": bid},
        "status": "preliminary", "type": _cc(SCT, "371530004", "Clinical consultation report"),
        "subject": {"reference": patient}, "encounter": {"reference": encounter}, "date": generated,
        "author": [{"reference": device, "display": "MedAssist AI (patient-reported, AI-structured)"}],
        "title": "Pre-consultation note (MedAssist AI)",
        "section": sections,
    }
    entries.insert(0, {"fullUrl": ref("composition"), "resource": composition})
    return {
        "resourceType": "Bundle", "id": _id(bid, "bundle"),
        "meta": {"profile": [NRCES + "DocumentBundle"], "lastUpdated": now.astimezone().isoformat(timespec="seconds")},
        "identifier": {"system": "urn:ietf:rfc:3986", "value": f"urn:uuid:{_id(bid, 'bundle')}"},
        "type": "document", "timestamp": now.astimezone().isoformat(timespec="seconds"),
        "entry": entries,
    }


def check_references(bundle: dict) -> list[str]:
    """Every reference inside the Bundle must point to an entry in it (a FHIR document is self-contained)."""
    urls = {e["fullUrl"] for e in bundle["entry"]}
    missing = []

    def walk(o):
        if isinstance(o, dict):
            r = o.get("reference")
            if isinstance(r, str) and r not in urls:
                missing.append(r)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(bundle)
    return missing
