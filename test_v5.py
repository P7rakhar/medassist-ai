"""v0.5 tests: doctor handoff note, doctor view API, database upgrade, comparison baselines."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db import Store  # noqa: E402
from backend.pipeline import MedAssistEngine  # noqa: E402
from tests.baselines import keyword_engine, no_context_engine  # noqa: E402

NOW = datetime(2026, 10, 2, 10, 5)
ENGINE = MedAssistEngine()


def _remove(path):
    try:
        os.unlink(path)
    except PermissionError:
        pass


def analyze(text, **kw):
    return ENGINE.analyze(text, 28.544, 77.333, now=NOW, log_case=False, **kw)


class TestHandoffNote(unittest.TestCase):
    def test_note_lists_present_denied_and_past(self):
        n = analyze("fever and body ache for 3 days, no vomiting, chest pain last year, I am diabetic")["handoff"]
        self.assertEqual(n["triage"]["level"] in ("LOW", "MODERATE", "HIGH", "UNCERTAIN"), True)
        self.assertIn("fever", [s["id"] for s in n["symptoms"]])
        self.assertIn("vomiting", [s["id"] for s in n["denied"]])
        self.assertIn("chest_pain", [s["id"] for s in n["past"]])
        self.assertEqual(n["details"]["duration_days"], 3)
        self.assertTrue(n["risk_factors"])

    def test_implied_parent_symptom_not_repeated(self):
        n = analyze("tez bukhar hai")["handoff"]
        ids = [s["id"] for s in n["symptoms"]]
        self.assertIn("high_fever", ids); self.assertNotIn("fever", ids)

    def test_answered_questions_are_marked_asked(self):
        n = analyze("fever", answers={"rash": False, "joint_pain": True})["handoff"]
        self.assertTrue(next(s for s in n["denied"] if s["id"] == "rash")["asked"])
        self.assertTrue(next(s for s in n["symptoms"] if s["id"] == "joint_pain")["asked"])

    def test_text_versions_for_whatsapp(self):
        n = analyze("मुझे बुखार है, उल्टी नहीं")["handoff"]
        self.assertIn("Says NO to", n["text"]["en"]); self.assertIn("Not a diagnosis", n["text"]["en"])
        self.assertIn("इनसे मना किया", n["text"]["hi"]); self.assertIn("निदान नहीं", n["text"]["hi"])

    def test_emergency_line(self):
        n = analyze("severe chest pain spreading to my left arm and sweating")["handoff"]
        self.assertTrue(n["triage"]["emergency"]); self.assertIn("112", n["text"]["en"])


class TestStoreUpgrade(unittest.TestCase):
    def test_old_database_gets_note_columns(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); tmp.close()
        con = sqlite3.connect(tmp.name)          # a v0.4 bookings table, without note / status
        con.execute("CREATE TABLE bookings (booking_id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL, doctor_name TEXT, clinic TEXT, "
                    "area TEXT, slot TEXT NOT NULL, slot_end TEXT, mode TEXT, patient_name TEXT, fee INTEGER, video_link TEXT, "
                    "created_at TEXT, UNIQUE (doctor_id, slot))")
        con.execute("INSERT INTO bookings (booking_id, doctor_id, slot) VALUES ('MA-OLD', 'D01', '2026-10-02T11:00')")
        con.commit(); con.close()
        st = Store(tmp.name)
        try:
            old = st.bookings()[0]
            self.assertIsNone(old["note"]); self.assertEqual(old["status"], "waiting")
            eng = MedAssistEngine(store=st)
            doc = eng.doctor_by_id["D02"]
            slot = eng.scheduler.free_slots(doc, NOW, limit=1)[0].isoformat(timespec="minutes")
            note = analyze("fever")["handoff"]
            b = eng.scheduler.book(doc, slot, "Asha", "in_person", now=NOW, note=note)
            eng.scheduler.set_status(b["booking_id"], "seen")
            st2 = Store(tmp.name)                                              # "restart"
            again = {x["booking_id"]: x for x in st2.bookings()}
            st2.close()
            self.assertEqual(again[b["booking_id"]]["note"]["triage"]["level"], note["triage"]["level"])
            self.assertEqual(again[b["booking_id"]]["status"], "seen")
        finally:
            st.close()
            _remove(tmp.name)


class TestSafetyFloor(unittest.TestCase):
    def test_chest_pain_with_acidity_is_never_low(self):
        r = analyze("I have chest pain and acidity")
        self.assertNotEqual(r["triage"]["level"], "LOW")
        self.assertTrue(any("never rated low" in x["en"] for x in r["triage"]["reasons"]))

    def test_denied_chest_pain_can_still_be_low(self):
        self.assertEqual(analyze("no chest pain, just a runny nose")["triage"]["level"], "LOW")


class TestBaselines(unittest.TestCase):
    def test_keyword_baseline_misreads_negation(self):
        text = "no fainting, no confusion, just feeling tired"
        kw = keyword_engine().analyze(text, 28.544, 77.333, now=NOW, log_case=False)
        full = analyze(text)
        self.assertIn("unconscious", [s["id"] for s in kw["symptoms"]])
        self.assertNotIn("unconscious", [s["id"] for s in full["symptoms"]])
        self.assertEqual(kw["triage"]["level"], "HIGH"); self.assertNotEqual(full["triage"]["level"], "HIGH")

    def test_no_context_ablation(self):
        r = no_context_engine().analyze("no fever, just cough", 28.544, 77.333, now=NOW, log_case=False)
        self.assertIn("fever", [s["id"] for s in r["symptoms"]])

    def test_negation_set(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("run_eval", Path(__file__).parent / "run_eval.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        res = mod.evaluate_context(MedAssistEngine())
        self.assertEqual(res["wrongly_counted"], 0); self.assertEqual(res["under_triage"], 0)
        self.assertEqual(res["triage_ok"], res["cases"])


try:
    from fastapi.testclient import TestClient
    HAVE_FASTAPI = True
except ImportError:  # pragma: no cover
    HAVE_FASTAPI = False


@unittest.skipUnless(HAVE_FASTAPI, "fastapi not installed")
class TestDoctorAPI(unittest.TestCase):
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
        _remove(cls.tmp.name)

    def _book(self, doctor_id, text, name):
        slots = self.client.get(f"/api/doctors/{doctor_id}/slots").json()
        taken = {b["slot"] for b in self.client.get("/api/bookings").json() if b["doctor_id"] == doctor_id}
        slot = next(s for s in slots if s not in taken)
        r = self.client.post("/api/book", json={"doctor_id": doctor_id, "slot": slot, "patient_name": name,
                                                "mode": "in_person", "case": {"text": text}})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_booking_carries_note_and_urgent_first(self):
        mild = self._book("D03", "runny nose and sneezing", "Mild Patient")
        urgent = self._book("D03", "severe chest pain and sweating", "Urgent Patient")
        self.assertEqual(mild["note"]["triage"]["level"], "LOW")
        q = self.client.get("/api/doctor/D03/appointments?order=urgency").json()["appointments"]
        self.assertEqual(q[0]["booking_id"], urgent["booking_id"])
        r = self.client.post(f"/api/bookings/{urgent['booking_id']}/status", json={"status": "seen"})
        self.assertEqual(r.json()["status"], "seen")
        q = self.client.get("/api/doctor/D03/appointments?order=urgency").json()["appointments"]
        self.assertEqual(q[-1]["booking_id"], urgent["booking_id"])          # seen patients move to the end

    def test_booking_without_case_still_works(self):
        slot = self.client.get("/api/doctors/D04/slots").json()[0]
        r = self.client.post("/api/book", json={"doctor_id": "D04", "slot": slot, "patient_name": "X", "mode": "in_person"})
        self.assertEqual(r.status_code, 200); self.assertIsNone(r.json()["note"])

    def test_unknown_ids(self):
        self.assertEqual(self.client.get("/api/doctor/NOPE/appointments").status_code, 404)
        self.assertEqual(self.client.get("/api/bookings/NOPE").status_code, 404)
        self.assertEqual(self.client.post("/api/bookings/NOPE/status", json={"status": "seen"}).status_code, 404)
        self.assertEqual(self.client.post("/api/bookings/NOPE/status", json={"status": "gone"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
