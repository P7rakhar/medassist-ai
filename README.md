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

Three sides of healthcare access, one system:
- **Patients** (`/`): voice or text in their own language, a consent notice first, a **Simple mode** with big buttons
  that reads every result aloud, and a one-page **doctor's note** they can send on **WhatsApp** or print.
- **Doctors** (`/doctor.html`): every booking arrives with that structured pre-consultation note (symptoms, what the
  patient said they do *not* have, duration, existing conditions, triage reasons, their own words), ordered by time
  or **most urgent first**. The doctor records their own triage level, which builds a **doctor-labelled dataset** from
  real use, and can download the note as an **HL7 FHIR R4** record shaped like ABDM's OP consultation record.
- **Health officers** (`/insights.html`): anonymised trends and outbreak alerts.

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
- Tests: `python -m unittest discover -s tests -v` (95 tests).
- Evaluation: `python tests/run_eval.py`: 60 team-written descriptions in 3 languages, 27 negation cases, a comparison
  with plain keyword matching, and **45 cases written and triage-labelled by physicians** (Semigran et al., BMJ 2015).
  Add `--db medassist.db` to also score the doctor-labelled cases collected in the doctor view.
- Retrain the second-opinion model: `pip install -r requirements-train.txt`, then
  `python training/train_model.py --csv Symptom2Disease.csv` (dataset from Kaggle, not included).
- Put it online for free: see **DEPLOY.md** (GitHub + Render.com, about 15 minutes, no Docker or payment).

## How it works

| Step | What happens | Code |
|---|---|---|
| 1. Voice / text input | Continuous browser speech recognition with auto-restart, live transcript, silence timer | `frontend/app.js` |
| 2. Language detection | Unicode script (10 Indian scripts) + Hinglish marker words | `backend/nlp.py` |
| 3. Normalisation | Unicode cleanup; every word turned into a spelling-tolerant phonetic key; Devanagari transliterated with Hindi schwa deletion | `backend/translit.py` |
| 4. Entity extraction | 968 trilingual phrases (longest match, typo-tolerant), body part × sensation composer ("dard pet mein"), **ConText** negation / uncertainty / history / family-history (NegEx algorithm with Hindi & Hinglish triggers), duration, pain score, temperature, oxygen saturation, age, existing conditions | `nlp.py`, `bodymap.py`, `context.py`, `data/context_triggers.json` |
| 5. Knowledge graph | 84 symptoms, 36 conditions (ICD-10 coded, each with a WHO/NHS source link), 14 specialties, 231 weighted edges, 968 phrases, 20 red-flag rules, 7 risk factors. Optional Neo4j backend | `knowledge_graph.py`, `graph_neo4j.py`, `data/knowledge_graph.json` |
| 6. Risk scoring | Red flags force HIGH; otherwise a 0–100 score from condition severity + duration, severity, age, temperature, existing conditions | `triage.py` |
| 7. Doctor matching | 0.30·specialty (cosine) + 0.20·distance (Haversine) + 0.15·rating (Bayesian) + 0.15·availability + 0.10·language + 0.10·cost | `matching.py` |
| 8. Clarifying questions | Safety screens first, then the questions with the highest **expected information gain** over the condition distribution, then missing details (since when, how bad, age, where the pain is) | `clarify.py` |
| Emergency warning signs | 20 red-flag rules, each citing its NHS (or WHO) page: meningitis signs, sudden confusion, unbearable pain or a hard tummy, one swollen leg (DVT), stiff jaw (tetanus), stroke, heart attack, oxygen ≤ 92% … | `data/knowledge_graph.json`, `triage.py` |
| Safety floor | Chest pain, breathlessness, blood in urine or stool, and oxygen 93–94% are never rated LOW | `triage.py` |
| Trained second opinion | Logistic regression trained on 1,200 public patient descriptions (Symptom2Disease, 24 diseases) using our NLP's symptom codes (+ English words). Shown beside the knowledge graph's ranking, never instead of it; disagreements are flagged in the doctor's note | `model.py`, `training/train_model.py` |
| Doctor handoff | Each analysis becomes a structured pre-consultation note (English + Hindi text for WhatsApp / print); the server re-creates it when a booking is made and stores it with the booking | `handoff.py`, `frontend/note.js`, `frontend/doctor.html` |
| Doctor-labelled cases | The doctor confirms or corrects the AI's triage (and adds a diagnosis); agreement statistics are shown live | `labels.py`, `db.py` |
| FHIR R4 export | Each note as a FHIR document Bundle with the NRCeS/ABDM `DocumentBundle` and `OPConsultRecord` profiles: Conditions (denied symptoms as `refuted`), LOINC-coded temperature / SpO2 / pain, a RiskAssessment with ICD-10-coded possible conditions, and the doctor's assessment | `fhir.py` |
| Storage & insights | SQLite: bookings (with notes) survive restarts; an anonymised case log feeds daily trends and outbreak alerts | `db.py`, `frontend/insights.html` |

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

**Compared with simpler systems.** The same cases go through the same knowledge graph and triage rules with
(a) plain keyword matching, the way a typical symptom checker reads text, and (b) MedAssist with only its ConText
step switched off. The difference is purely in understanding the text:

| System | 60 general cases: triage OK | Emergencies under-rated | 27 negation cases: denied symptoms counted | Over-triage |
|---|---|---|---|---|
| Keyword matching | 87% | 3 of 14 | 32 of 33 | 6 |
| MedAssist without ConText | 100% | 0 of 14 | 32 of 33 | 6 |
| **MedAssist AI** | **100%** | **0 of 14** | **0 of 33** | **0** |

The 27 negation cases (`tests/context_cases.json`), e.g. "no fainting, no confusion, just feeling tired", are labelled
by what the sentence literally says, so they need no clinical judgement.

**Read these honestly:** the same team wrote the cases and the engine, so they show the system does what we
designed. They are not a clinical validation. Real patients phrase things we haven't anticipated.

### Doctor-written benchmark (independent of the team)

The 45 standardised vignettes from Semigran et al., *BMJ* 2015 were written and triage-labelled by physicians
(15 emergency, 15 see-a-doctor, 15 self-care). They are the usual benchmark for symptom checkers
(`tests/doctor_vignettes.json`, from [medask-benchmark](https://github.com/medaks/medask-benchmark), MIT).

| System | Correct triage | Emergencies rated HIGH |
|---|---|---|
| MedAssist v0.5 | 18 / 45 (40%) | 4 / 15 |
| **MedAssist v0.6** (NHS warning-sign rules, clinical-text parsing fixes) | **28 / 45 (62%)** | **12 / 15** |
| 23 symptom-checker apps (Semigran et al., 2015) | 57% | 80% |

The v0.5 run exposed real safety gaps (meningitis signs, sudden confusion and a kidney stone were rated LOW). We fixed
them with warning-sign rules taken from NHS guidance and fixed parsing bugs the cases revealed (ages read as
temperatures, "denies A, B, C" lists, "3-day history of"). **Because the fixes came after seeing the misses, the v0.6
number is no longer a blind test.** Still missed as emergencies: malaria after travel, haemolytic uraemic syndrome and
Rocky Mountain spotted fever. The vignettes are written in doctors' language with exam and lab findings, so they are
harder for a patient-language system than real patient input; that is also why most remaining errors are
see-a-doctor cases rated self-care. The doctor view now collects doctor-labelled cases from real use for the next
blind evaluation.

### Trained second-opinion model

| Test | Result |
|---|---|
| Held-out 20% of Symptom2Disease (240 descriptions never used in training) | 97% correct, top-3 100% |
| 5-fold cross-validation | 97.3% ± 0.6% |
| Same split, symptom codes only (what Hindi / Hinglish input uses) | 78% correct, top-3 91% |
| Our own 23 cases whose disease the model knows (English, Hindi, Hinglish) | top-1 8 / 23, top-3 18 / 23 |

The dataset's own split is easy (its descriptions are templated); on our short, multilingual descriptions the model is
much weaker than the knowledge graph. That is why it is a second opinion: it never changes triage, and disagreements go
to the doctor.

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
| POST | `/api/book` | `{doctor_id, slot, patient_name, mode, case?}` → booking (saved in SQLite); `case` = the analyze request, used to attach the doctor's note |
| GET | `/api/doctors`, `/api/doctors/{id}/slots`, `/api/bookings`, `/api/bookings/{id}` | Directory, free slots, bookings |
| GET | `/api/doctor/{id}/appointments?order=time\|urgency` | A doctor's appointments with pre-consultation notes |
| POST | `/api/bookings/{id}/status` | `{status: waiting\|seen}` |
| POST | `/api/bookings/{id}/review` | `{level: LOW\|MODERATE\|HIGH, condition?, comment?}`: the doctor's own triage |
| GET | `/api/labelled-cases` | Doctor-labelled cases (no names) + AI–doctor agreement |
| GET | `/api/bookings/{id}/fhir` | The note as an HL7 FHIR R4 document Bundle (`application/fhir+json`) |
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
- The doctor view has no sign-in in this demo. Production would verify doctors (e.g. ABDM Healthcare Professionals
  Registry) and show each doctor only their own patients. "Send on WhatsApp" opens WhatsApp with the note ready; it is
  not a WhatsApp chatbot.
- Data handling follows the principles of India's Digital Personal Data Protection Act, 2023 (consent first, minimum
  data, purpose-limited), but has not been legally reviewed.
- FHIR export follows the NRCeS (ABDM) profiles and is checked in our tests (structure, references, codes, time zones);
  it has not yet been run through the official FHIR validator or the ABDM sandbox. ABHA numbers and facility IDs need
  ABDM sandbox registration (1–2 working days), planned after the technical round. Symptoms are sent as text, not yet
  SNOMED-coded.
- The second-opinion model is trained on a public Kaggle dataset (check its licence before commercial use); a model
  trained on consented, doctor-labelled Indian cases is the next step.
- Not yet built: Bhashini / AI4Bharat models for all 22 scheduled languages (planned for the next round), a
  phone-call / IVR line for basic phones, a WhatsApp chatbot, ABHA linking.

## Credits

- NegEx / ConText algorithms: Chapman et al. (2001), Harkema et al. (2009). English trigger ideas adapted from
  [negspacy](https://github.com/kvthr/negspacy) (MIT).
- Graph schema style from [Hetionet](https://github.com/hetio/hetionet) (Disease–PRESENTS–Symptom).
- Condition information and emergency warning signs: NHS condition pages and WHO fact sheets (links in
  `knowledge_graph.json`); oxygen thresholds from NHS England's home pulse-oximetry guidance.
- Doctor-written benchmark: Semigran HL, Linder JA, Gidengil C, Mehrotra A. *Evaluation of symptom checkers for self
  diagnosis and triage: audit study.* BMJ 2015;351:h3480. Machine-readable copy: medask-benchmark (MIT).
- Training data: Symptom2Disease (Kaggle, niyarrbarman/symptom2disease).
- FHIR profiles: NRCeS FHIR Implementation Guide for ABDM (`DocumentBundle`, `OPConsultRecord`).
