"""
Tests for the v0.4 upgrades: ConText NLP, body-part composer, transliteration,
clarifying questions, risk factors, SQLite storage, API compatibility and the
optional Neo4j backend.   Run:  python -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest
from datetime import datetime

from backend.clarify import entropy, information_gain
from backend.db import Store
from backend.pipeline import MedAssistEngine
from backend.translit import deva_to_roman, phonetic_key

NOW = datetime(2026, 10, 2, 10, 5)
ENGINE = MedAssistEngine()
X = ENGINE.extractor


def ext(text):
    return X.extract(text, NOW)


class TestTransliteration(unittest.TestCase):
    def test_devanagari_to_roman_with_schwa_deletion(self):
        self.assertEqual(deva_to_roman("बुखार"), "bukhaar")
        self.assertEqual(deva_to_roman("धड़कन"), "dhadkan")
        self.assertEqual(deva_to_roman("दस्त"), "dast")

    def test_spelling_variants_share_a_key(self):
        self.assertEqual(len({phonetic_key(w) for w in ["bukhaar", "bukhar", "बुखार"]}), 1)
        self.assertEqual(phonetic_key("khaansi"), phonetic_key("khansi"))
        self.assertEqual(phonetic_key("नहीं"), phonetic_key("nahin"))


class TestConText(unittest.TestCase):
    def test_negation_stops_at_but(self):
        e = ext("no fever but bad cough")
        self.assertEqual(e.present, ["cough"]); self.assertEqual(e.absent, ["fever"])
        self.assertEqual(e.severity, "severe")

    def test_negated_list_with_or(self):
        self.assertEqual(set(ext("I don't have fever, cough or cold").absent), {"fever", "cough", "runny_nose"})

    def test_comma_without_list_ends_scope(self):
        e = ext("no fever, headache since 2 days")
        self.assertEqual(e.present, ["headache"]); self.assertEqual(e.duration_days, 2)

    def test_hindi_backward_negation_respects_copula(self):
        e = ext("bukhar hai aur khansi nahi hai")
        self.assertEqual(e.present, ["fever"]); self.assertEqual(e.absent, ["cough"])
        self.assertEqual(set(ext("mujhe bukhar aur khansi nahi hai").absent), {"fever", "cough"})

    def test_pseudo_negation_keeps_symptom(self):
        self.assertIn("fever", ext("my fever is not going down").present)
        self.assertIn("fever", ext("bukhar nahi utar raha 4 din se").present)

    def test_uncertainty_halves_weight(self):
        e = ext("shayad bukhar hai")
        self.assertEqual(e.weights["fever"], 0.5)
        self.assertEqual(ext("maybe I have fever").weights["fever"], 0.5)

    def test_historical_and_family(self):
        e = ext("the fever went away but cough is still there")
        self.assertEqual(e.present, ["cough"]); self.assertEqual(e.historical, ["fever"])
        self.assertEqual(ext("family history of diabetes").family_history, ["diabetes"])
        self.assertEqual(ext("I had dengue last year").condition_mentions[0]["status"], "past")


class TestComposer(unittest.TestCase):
    def test_free_word_order(self):
        self.assertIn("abdominal_pain", ext("my stomach hurts a lot").present)
        self.assertIn("abdominal_pain", ext("dard ho raha hai pet mein").present)
        self.assertIn("headache", ext("सिर में बहुत दर्द है").present)

    def test_shared_sensation_and_qualifiers(self):
        self.assertEqual(set(ext("head and stomach pain").present), {"headache", "abdominal_pain"})
        self.assertIn("radiating_pain", ext("pain in my left arm and chest").present)
        self.assertIn("lower_right_abd_pain", ext("pain in the lower right side of my stomach").present)

    def test_negation_inside_composite(self):
        e = ext("my head is not hurting but my throat is sore")
        self.assertEqual(e.absent, ["headache"]); self.assertIn("sore_throat", e.present)

    def test_pain_without_location_is_reported(self):
        self.assertEqual(ext("I have pain").unplaced_sensations, ["pain"])


class TestExtras(unittest.TestCase):
    def test_pain_score_and_weekday(self):
        e = ext("pain 8/10 in my back since monday")
        self.assertEqual(e.pain_score, 8); self.assertEqual(e.severity, "severe")
        self.assertEqual(e.duration_days, 4)                  # NOW is a Friday
        self.assertIn("back_pain", e.present)

    def test_prolonged_cough_rule(self):
        self.assertIn("prolonged_cough", ext("cough for 3 weeks with night sweats").present)

    def test_risk_factors(self):
        self.assertEqual([r["id"] for r in ext("sugar ki bimari hai").risk_factors], ["diabetes"])

    def test_unrecognised_words_reported(self):
        self.assertIn("weird", ext("I feel weird today").unrecognised)


class TestClarify(unittest.TestCase):
    def test_entropy(self):
        self.assertAlmostEqual(entropy({"a": 0.5, "b": 0.5}), 1.0)

    def test_information_gain_prefers_discriminating_symptom(self):
        gains = dict(information_gain(ENGINE.kg, {"fever": 1.0, "joint_pain": 1.0}, [], {"fever", "joint_pain"}))
        self.assertGreater(gains["eye_pain"], gains.get("sneezing", 0))

    def test_safety_question_first(self):
        r = ENGINE.analyze("fever and body ache since 2 days", 28.544, 77.333, now=NOW, log_case=False)
        first = [q for q in r["questions"] if q["type"] == "symptom"][0]
        self.assertEqual(first["reason"], "safety"); self.assertEqual(first["id"], "bleeding_gums")

    def test_no_questions_in_an_emergency(self):
        r = ENGINE.analyze("chest pain and sweating", 28.544, 77.333, now=NOW, log_case=False)
        self.assertTrue(r["triage"]["emergency"]); self.assertEqual(r["questions"], [])

    def test_yes_answer_can_escalate_and_no_answer_is_denied(self):
        r = ENGINE.analyze("fever and body ache", 28.544, 77.333, now=NOW, answers={"bleeding_gums": True}, log_case=False)
        self.assertEqual(r["triage"]["level"], "HIGH")
        r = ENGINE.analyze("fever", 28.544, 77.333, now=NOW, answers={"chills": False}, log_case=False)
        self.assertIn("chills", [s["id"] for s in r["negated"]])

    def test_location_question_for_unplaced_pain(self):
        r = ENGINE.analyze("I have pain", 28.544, 77.333, now=NOW, log_case=False)
        self.assertEqual(r["questions"][0]["type"], "location")

    def test_slots_override(self):
        r = ENGINE.analyze("headache", 28.544, 77.333, now=NOW, slots={"duration_days": 21, "age": 70}, log_case=False)
        self.assertEqual(r["duration_days"], 21); self.assertEqual(r["age"], 70)


class TestRiskAndRedFlags(unittest.TestCase):
    def test_pregnancy_warning(self):
        r = ENGINE.analyze("I am 7 months pregnant and have swelling in my legs", 28.544, 77.333, now=NOW, log_case=False)
        self.assertEqual(r["triage"]["level"], "HIGH")

    def test_risk_factor_adds_points(self):
        base = ENGINE.analyze("headache since yesterday", 28.544, 77.333, now=NOW, log_case=False)["triage"]["score"]
        risky = ENGINE.analyze("headache since yesterday, I have heart disease", 28.544, 77.333, now=NOW, log_case=False)["triage"]["score"]
        self.assertGreater(risky, base)

    def test_new_conditions_present(self):
        r = ENGINE.analyze("my eyes are yellow and urine is dark", 28.544, 77.333, now=NOW, log_case=False)
        self.assertEqual(r["conditions"][0]["id"], "viral_hepatitis")
        self.assertTrue(r["conditions"][0]["icd10"])
        self.assertTrue(r["conditions"][0]["info_source"].startswith("https://"))


def _remove(path):
    """Delete a temporary database; on Windows a file can only be deleted once every connection is closed."""
    try:
        os.unlink(path)
    except PermissionError:
        pass


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); self.tmp.close()
        self.stores = []

    def tearDown(self):
        for st in self.stores:
            st.close()
        _remove(self.tmp.name)

    def open_store(self):
        st = Store(self.tmp.name)
        self.stores.append(st)
        return st

    def test_bookings_survive_restart(self):
        s1 = self.open_store()
        e1 = MedAssistEngine(store=s1)
        doc = e1.doctor_by_id["D01"]
        slot = e1.scheduler.free_slots(doc, NOW, limit=1)[0].isoformat(timespec="minutes")
        e1.scheduler.book(doc, slot, "Test", "in_person", now=NOW)
        e2 = MedAssistEngine(store=self.open_store())          # "restart"
        self.assertIn(("D01", slot), e2.scheduler.booked)

    def test_outbreak_alert_on_demo_data(self):
        s = self.open_store()
        s.seed_demo(ENGINE, now=NOW)
        alerts = s.insights(now=NOW)["alerts"]
        self.assertTrue(any(a["condition"] == "dengue" and "Dadri" in a["area"] for a in alerts))
        self.assertGreater(s.clear_demo(), 0)
        self.assertEqual(s.insights(now=NOW)["total"], 0)

    def test_case_log_has_no_free_text(self):
        s = self.open_store()
        e = MedAssistEngine(store=s)
        e.analyze("my name is Ravi and I have fever", 28.5441, 77.3331, now=NOW)
        row = dict(s.conn.execute("SELECT * FROM cases").fetchone())
        self.assertNotIn("Ravi", str(row)); self.assertEqual(row["lat"], 28.54)


class TestNeo4jBackend(unittest.TestCase):
    def test_cypher_candidates_match_memory(self):
        """A fake driver returning the same edges must give identical results to the in-memory graph."""
        from backend import graph_neo4j
        kg = MedAssistEngine().kg
        expected = [(c.id, c.likelihood) for c in kg.query({"fever": 1.0, "joint_pain": 1.0}, top_k=5)]

        class FakeResult:
            def __init__(self, rows): self.rows = rows
            def data(self): return self.rows

        class FakeSession:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def run(self, cypher, present):
                rows = [{"id": cid, "edges": [[s, w] for s, w in c["symptoms"].items()]}
                        for cid, c in kg.conditions.items() if set(c["symptoms"]) & set(present)]
                return FakeResult(rows)

        class FakeDriver:
            def session(self): return FakeSession()

        graph_neo4j._attach(kg, FakeDriver())
        self.assertEqual([(c.id, c.likelihood) for c in kg.query({"fever": 1.0, "joint_pain": 1.0}, top_k=5)], expected)

    def test_not_configured_means_memory(self):
        from backend import graph_neo4j
        os.environ.pop("NEO4J_URI", None)
        self.assertEqual(graph_neo4j.connect_if_configured(MedAssistEngine())["backend"], "in-memory")


try:
    from fastapi.testclient import TestClient
    HAVE_FASTAPI = True
except ImportError:  # pragma: no cover
    HAVE_FASTAPI = False


@unittest.skipUnless(HAVE_FASTAPI, "FastAPI not installed")
class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); cls.tmp.close()
        os.environ["MEDASSIST_DB"] = cls.tmp.name
        import importlib
        import sys
        import backend.db
        importlib.reload(backend.db)                      # pick up the temporary database path
        if "backend.main" in sys.modules:
            importlib.reload(sys.modules["backend.main"])
        import backend.main
        cls.client = TestClient(backend.main.app)

    @classmethod
    def tearDownClass(cls):
        import backend.main
        backend.main.store.close()
        os.environ.pop("MEDASSIST_DB", None)
        _remove(cls.tmp.name)

    def test_v1_request_still_works(self):
        r = self.client.post("/api/analyze", json={"text": "fever and cough", "extra_symptoms": ["bleeding_gums"]})
        self.assertEqual(r.status_code, 200); self.assertEqual(r.json()["triage"]["level"], "HIGH")

    def test_answers_and_slots(self):
        r = self.client.post("/api/analyze", json={"text": "headache", "answers": {"face_droop": False},
                                                   "slots": {"duration_days": 2, "severity": "mild"}}).json()
        self.assertEqual(r["severity"], "mild"); self.assertIn("face_droop", [s["id"] for s in r["negated"]])

    def test_bad_slot_rejected(self):
        self.assertEqual(self.client.post("/api/analyze", json={"text": "x", "slots": {"severity": "huge"}}).status_code, 422)

    def test_insights_and_kg_endpoints(self):
        self.assertEqual(self.client.post("/api/insights/demo-data").status_code, 200)
        self.assertTrue(self.client.get("/api/insights").json()["alerts"])
        self.assertEqual(self.client.get("/api/knowledge-graph").json()["stats"]["conditions"], 36)


if __name__ == "__main__":
    unittest.main()


class TestEvaluationSet(unittest.TestCase):
    """Guards against regressions on the 60 team-written cases (see tests/run_eval.py)."""

    def test_no_under_triage_and_high_accuracy(self):
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location("run_eval", pathlib.Path(__file__).parent / "run_eval.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        res = mod.evaluate(MedAssistEngine())
        self.assertEqual(res["under_triage"], 0)
        self.assertGreaterEqual(res["triage_accuracy"], 0.9)
        self.assertGreaterEqual(res["top3_accuracy"], 0.9)
