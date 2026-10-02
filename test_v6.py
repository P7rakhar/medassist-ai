"""v0.6 tests: NHS warning-sign rules, clinical-text parsing, doctor benchmark, doctor reviews,
FHIR R4 export and the trained second-opinion model."""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.fhir import booking_bundle, check_references  # noqa: E402
from backend.labels import agreement, labelled_cases  # noqa: E402
from backend.model import SecondOpinion  # noqa: E402
from backend.pipeline import MedAssistEngine  # noqa: E402

NOW = datetime(2026, 10, 2, 10, 5)
ENGINE = MedAssistEngine()


def analyze(text, **kw):
    return ENGINE.analyze(text, 28.544, 77.333, now=NOW, log_case=False, **kw)


def level(text):
    return analyze(text)["triage"]["level"]


def ids(r, key="symptoms"):
    return [s["id"] for s in r[key]]


class TestNHSWarningSigns(unittest.TestCase):
    def test_meningitis_signs(self):
        self.assertEqual(level("fever and a stiff neck since morning"), "HIGH")
        self.assertEqual(level("tez bukhar hai aur gardan akad gayi hai"), "HIGH")
        self.assertEqual(level("fever, severe headache and bright light hurts my eyes"), "HIGH")

    def test_stiff_neck_alone_is_not_an_emergency(self):
        r = analyze("stiff neck after sleeping in a bad position")
        self.assertEqual(r["triage"]["level"], "LOW"); self.assertEqual(r["conditions"][0]["id"], "neck_strain")

    def test_sudden_confusion(self):
        self.assertEqual(level("my father is suddenly confused and not making sense"), "HIGH")

    def test_everyday_confusion_words_are_not_emergencies(self):
        self.assertNotEqual(level("I am confused about which medicine to take for my cold"), "HIGH")
        self.assertNotEqual(level("mann mein uljhan rehti hai aur neend nahi aati"), "HIGH")

    def test_one_leg_swelling_dvt(self):
        self.assertEqual(level("my left leg is swollen and painful since 3 days"), "HIGH")
        self.assertEqual(level("ek pair mein sujan aur dard hai"), "HIGH")
        self.assertNotEqual(level("both legs are a little swollen in the evening"), "HIGH")

    def test_tetanus_and_severe_pain(self):
        self.assertEqual(level("cut my hand while gardening, now my jaw is stiff and I have painful spasms"), "HIGH")
        self.assertEqual(level("pet mein dard hai, dard sahan nahi ho raha"), "HIGH")

    def test_oxygen_saturation(self):
        r = analyze("cough and fever, my oximeter shows oxygen 90")
        self.assertEqual(r["spo2"], 90); self.assertEqual(r["triage"]["level"], "HIGH")
        self.assertNotEqual(level("mild cough, SpO2 94%"), "LOW")

    def test_blood_in_stool(self):
        self.assertNotEqual(level("blood in stool for 2 days"), "LOW")
        self.assertEqual(level("fever and blood in stool"), "HIGH")

    def test_every_rule_cites_a_source(self):
        missing = [r["id"] for r in ENGINE.kg.red_flag_rules if r["id"] != "mental_health" and not r.get("source")]
        self.assertEqual(missing, [])


class TestClinicalTextParsing(unittest.TestCase):
    def test_age_and_heart_rate_are_not_temperatures(self):
        self.assertIsNone(analyze("A 40-year-old woman with itching")["temperature_f"])
        self.assertEqual(analyze("heart rate 105 bpm, temperature of 100.1°F")["temperature_f"], 100.1)
        self.assertEqual(analyze("bukhar 102 hai")["temperature_f"], 102.0)

    def test_denies_list(self):
        r = analyze("She denies any fever, chills, nausea, vomiting, back pain")
        self.assertEqual(ids(r), []); self.assertEqual(set(ids(r, "negated")), {"fever", "chills", "nausea", "vomiting", "back_pain"})

    def test_plain_no_keeps_comma_rule(self):
        r = analyze("no fever, headache since morning")
        self.assertIn("headache", ids(r)); self.assertIn("fever", ids(r, "negated"))

    def test_day_history_is_not_past(self):
        r = analyze("a 3-day history of fever and productive cough")
        self.assertIn("fever", ids(r)); self.assertEqual(ids(r, "historical"), [])
        self.assertIn("asthma_copd", [x["id"] for x in analyze("history of asthma, now cough")["risk_factors"]])

    def test_afebrile(self):
        self.assertNotIn("fever", ids(analyze("afebrile, with a cough")))


class TestDoctorBenchmark(unittest.TestCase):
    def test_semigran_floor(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("run_eval", Path(__file__).parent / "run_eval.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        d = mod.evaluate_doctor(MedAssistEngine())
        self.assertEqual(d["cases"], 45)
        self.assertGreaterEqual(d["correct"], 28)            # 18/45 before the v0.6 rules
        self.assertGreaterEqual(d["emergency_high"], 12)     # 4/15 before


def _booking(engine, text="mujhe 3 din se tez bukhar hai, ulti nahi hui, pichle saal pathri thi, oxygen 93, pain 7/10"):
    doc = engine.doctor_by_id["D01"]
    slot = engine.scheduler.free_slots(doc, NOW, limit=1)[0].isoformat(timespec="minutes")
    note = engine.analyze(text, 28.544, 77.333, now=NOW, log_case=False)["handoff"]
    return doc, engine.scheduler.book(doc, slot, "Asha", "video", now=NOW, note=note)


class TestReviewsAndFHIR(unittest.TestCase):
    def setUp(self):
        self.engine = MedAssistEngine()

    def test_review_becomes_labelled_case(self):
        _, b = _booking(self.engine)
        self.engine.scheduler.set_review(b["booking_id"], "HIGH", "Dengue fever", "NS1 ordered", now=NOW)
        cases = labelled_cases(list(self.engine.scheduler.bookings.values()))
        self.assertEqual(len(cases), 1)
        self.assertNotIn("Asha", str(cases))                 # no patient names in labelled data
        s = agreement(cases)
        self.assertEqual(s["cases"], 1); self.assertEqual(s["agree"], int(cases[0]["ai_level"] == "HIGH"))

    def test_fhir_bundle_structure(self):
        doc, b = _booking(self.engine)
        self.engine.scheduler.set_review(b["booking_id"], "MODERATE", "Viral fever", None, now=NOW)
        bundle = booking_bundle(b, doc, now=NOW)
        self.assertEqual(bundle["resourceType"], "Bundle"); self.assertEqual(bundle["type"], "document")
        self.assertIn("DocumentBundle", bundle["meta"]["profile"][0])
        comp = bundle["entry"][0]["resource"]
        self.assertEqual(comp["resourceType"], "Composition")
        self.assertIn("OPConsultRecord", comp["meta"]["profile"][0])
        self.assertEqual(comp["type"]["coding"][0]["code"], "371530004")
        for k in ("status", "type", "subject", "encounter", "date", "author", "title"):
            self.assertIn(k, comp)
        self.assertEqual(check_references(bundle), [])
        res = [e["resource"] for e in bundle["entry"]]
        self.assertEqual(len({e["fullUrl"] for e in bundle["entry"]}), len(res))
        refuted = [r for r in res if r["resourceType"] == "Condition" and r["verificationStatus"]["coding"][0]["code"] == "refuted"]
        self.assertTrue(any(r["code"]["text"] == "Vomiting" for r in refuted))
        codes = {r["code"]["coding"][0]["code"] for r in res if r["resourceType"] == "Observation"}
        self.assertTrue({"59408-5", "72514-3"} <= codes)
        self.assertTrue(any(r["resourceType"] == "RiskAssessment" and r["status"] == "final" for r in res))   # doctor's review
        tz = re.compile(r"T\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        self.assertRegex(comp["date"], tz); self.assertRegex(bundle["timestamp"], tz)

    def test_no_note_no_fhir(self):
        doc = self.engine.doctor_by_id["D02"]
        slot = self.engine.scheduler.free_slots(doc, NOW, limit=1)[0].isoformat(timespec="minutes")
        b = self.engine.scheduler.book(doc, slot, "X", "in_person", now=NOW)
        with self.assertRaises(ValueError):
            booking_bundle(b, doc, now=NOW)


class TestSecondOpinionModel(unittest.TestCase):
    def test_model_loads_with_metrics(self):
        m = SecondOpinion()
        self.assertTrue(m.ok); self.assertEqual(len(m.labels), 24)
        self.assertGreaterEqual(m.metrics["held_out"]["accuracy"], 0.9)

    def test_hinglish_dengue_uses_symptom_codes(self):
        so = analyze("mujhe 3 din se tez bukhar hai, aankhon ke peeche dard aur jodon mein dard")["second_opinion"]
        self.assertEqual(so["top"][0]["label"], "Dengue"); self.assertTrue(so["agrees"]); self.assertFalse(so["used_words"])

    def test_model_never_changes_triage(self):
        r = analyze("severe chest pain spreading to my left arm and sweating")
        self.assertEqual(r["triage"]["level"], "HIGH")


try:
    from fastapi.testclient import TestClient
    HAVE_FASTAPI = True
except ImportError:  # pragma: no cover
    HAVE_FASTAPI = False


@unittest.skipUnless(HAVE_FASTAPI, "fastapi not installed")
class TestV6API(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); cls.tmp.close()
        os.environ["MEDASSIST_DB"] = cls.tmp.name
        import importlib
        import backend.db
        importlib.reload(backend.db)
        if "backend.main" in sys.modules:
            importlib.reload(sys.modules["backend.main"])
        import backend.main
        cls.main = backend.main
        cls.client = TestClient(backend.main.app)

    @classmethod
    def tearDownClass(cls):
        cls.main.store.close()
        os.environ.pop("MEDASSIST_DB", None)
        try:
            os.unlink(cls.tmp.name)
        except PermissionError:
            pass

    def test_review_fhir_and_labelled_endpoints(self):
        slot = self.client.get("/api/doctors/D05/slots").json()[0]
        b = self.client.post("/api/book", json={"doctor_id": "D05", "slot": slot, "patient_name": "Ravi", "mode": "in_person",
                                                "case": {"text": "fever and a stiff neck"}}).json()
        r = self.client.post(f"/api/bookings/{b['booking_id']}/review", json={"level": "HIGH", "condition": "Meningitis"})
        self.assertEqual(r.status_code, 200); self.assertEqual(r.json()["doctor_level"], "HIGH")
        self.assertEqual(self.client.post(f"/api/bookings/{b['booking_id']}/review", json={"level": "SEVERE"}).status_code, 422)
        lab = self.client.get("/api/labelled-cases").json()
        self.assertEqual(lab["stats"]["cases"], 1); self.assertEqual(lab["stats"]["agree"], 1)
        f = self.client.get(f"/api/bookings/{b['booking_id']}/fhir")
        self.assertEqual(f.status_code, 200); self.assertIn("fhir+json", f.headers["content-type"])
        self.assertEqual(self.client.get("/api/bookings/NOPE/fhir").status_code, 404)


if __name__ == "__main__":
    unittest.main()
