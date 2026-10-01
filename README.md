---
title: MedAssist AI
emoji: 🩺
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Multilingual AI symptom triage and doctor matching
---

# MedAssist AI — Team Neuraxis

AI-based healthcare accessibility prototype for **Global Innoventure Hackathon 2026, Problem Statement 5**.

Speak or type your symptoms in **English, Hindi or Hinglish**. MedAssist understands them, including "no fever",
"maybe", "it went away", "my stomach hurts" and spelling variants. It reasons over a medical knowledge graph and
asks the most useful follow-up questions. Then it gives a **Low / Moderate / High / Uncertain** triage with
reasons, and ranks doctors with an explainable formula so you can book a clinic visit or video consult.
A separate **Insights** page shows health officers anonymised trends and outbreak alerts.

## Run it (Windows / macOS / Linux)

Needs Python 3.10 or newer.

```bash
cd medassist-ai
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000**. The API docs (Swagger) are at **/docs** and the health-officer dashboard is at **/insights.html**.

- Use **Chrome or Edge** for voice. Pick EN or हिं next to the mic for the language you'll speak. Voice keeps
  listening through pauses and stops when you press **Stop** or after 8 seconds of silence.
- Tests: `python -m unittest discover -s tests -v` (59 tests).
- Evaluation: `python tests/run_eval.py` (60 patient descriptions in 3 languages).
- Put it online for free: see **DEPLOY.md** (Hugging Face Spaces, about 10 minutes).

## How it works

| Step | What happens | Code |
|---|---|---|
| 1. Voice / text input | Continuous browser speech recognition with auto-restart, live transcript, silence timer | `frontend/app.js` |
| 2. Language detection | Unicode script (10 Indian scripts) + Hinglish marker words | `backend/nlp.py` |
| 3. Normalisation | Unicode cleanup; every word turned into a spelling-tolerant phonetic key; Devanagari transliterated with Hindi schwa deletion | `backend/translit.py` |
| 4. Entity extraction | 855 trilingual phrases (longest match, typo-tolerant), body part × sensation composer ("dard pet mein"), **ConText** negation / uncertainty / history / family-history (NegEx algorithm with Hindi & Hinglish triggers), duration, pain score, temperature, age, existing conditions | `nlp.py`, `bodymap.py`, `context.py`, `data/context_triggers.json` |
| 5. Knowledge graph | 78 symptoms, 32 conditions (ICD-10 coded, each with a WHO/NHS source link), 14 specialties, 203 weighted edges, 13 red-flag rules, 7 risk factors. Optional Neo4j backend | `knowledge_graph.py`, `graph_neo4j.py`, `data/knowledge_graph.json` |
| 6. Risk scoring | Red flags force HIGH; otherwise a 0–100 score from condition severity + duration, severity, age, temperature, existing conditions | `triage.py` |
| 7. Doctor matching | 0.30·specialty (cosine) + 0.20·distance (Haversine) + 0.15·rating (Bayesian) + 0.15·availability + 0.10·language + 0.10·cost | `matching.py` |
| 8. Clarifying questions | Safety screens first, then the questions with the highest **expected information gain** over the condition distribution, then missing details (since when, how bad, age, where the pain is) | `clarify.py` |
| Storage & insights | SQLite: bookings survive restarts; an anonymised case log feeds daily trends and outbreak alerts | `db.py`, `frontend/insights.html` |

The core engine is **fully offline**: no internet, GPU or API key. A typical analysis takes about 10–25 ms.

### Measured results (team-written test set)

`python tests/run_eval.py` on 60 descriptions (20 English, 20 Hindi, 20 Hinglish) written by the team, each with the
triage level(s) and condition we consider clinically reasonable:

| Metric | Result |
|---|---|
| Triage level acceptable | 60 / 60 |
| Emergencies rated lower than HIGH (under-triage) | 0 of 14 |
| Non-emergencies rated HIGH (over-triage) | 0 |
| Expected condition ranked first | 49 / 55 |
| Expected condition in the top 3 | 55 / 55 |

**Read these honestly:** the same team wrote the cases and the engine, so they show the system does what we
designed. They are not a clinical validation. Real patients phrase things we haven't anticipated. The next step is
cases written and labelled by doctors.

### Optional extras

```bash
# LLM fallback for unusual phrasing / other languages (Windows PowerShell)
$env:MEDASSIST_LLM_API_KEY="your-groq-key"; python run.py

# Neo4j graph backend (e.g. a free AuraDB instance)
pip install -r requirements-optional.txt
$env:NEO4J_URI="neo4j+s://xxxx.databases.neo4j.io"; $env:NEO4J_USER="neo4j"; $env:NEO4J_PASSWORD="..."; python run.py
```
If either is missing or fails, the app falls back to the offline engine automatically. `/api/health` shows which backend is active.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/analyze` | `{text, lat, lon, age?, mode, answers: {symptom_id: bool}, slots: {duration_days, severity, age}}` → triage, conditions, doctors, next questions, 8-step trace |
| POST | `/api/book` | `{doctor_id, slot, patient_name, mode}` → booking (saved in SQLite) |
| GET | `/api/doctors`, `/api/doctors/{id}/slots`, `/api/bookings` | Directory, free slots, bookings |
| GET | `/api/insights?days=14` | Anonymised statistics + outbreak alerts |
| POST / DELETE | `/api/insights/demo-data` | Add / remove clearly-flagged simulated cases |
| GET | `/api/knowledge-graph`, `/api/knowledge-graph/cypher` | Graph contents with ICD-10 codes; Neo4j Cypher export |
| GET | `/api/health`, `/api/meta` | Status and UI metadata |

CORS is open so other teams' systems can call the API during common-problem integration.

## Honest scope

- Doctors, clinics, ratings and slot occupancy are **synthetic demo data** (Delhi-NCR). Production would use the ABDM
  Health Facility Registry and Healthcare Professional Registry.
- Knowledge-graph weights are team estimates based on the linked WHO/NHS pages; they need clinician review. MedAssist
  gives triage guidance, not a diagnosis.
- Voice recognition is the browser's (Google's in Chrome) and needs internet; the analysis itself does not.
- Not yet built: React Native app, WhatsApp/IVR, live-translated video, ABDM/ABHA integration, wearables, on-device models.

## Credits

- NegEx / ConText algorithms: Chapman et al. (2001), Harkema et al. (2009). English trigger ideas adapted from
  [negspacy](https://github.com/kvthr/negspacy) (MIT).
- Graph schema style from [Hetionet](https://github.com/hetio/hetionet) (Disease–PRESENTS–Symptom).
- Condition information: WHO fact sheets and NHS condition pages (links in `knowledge_graph.json`).
