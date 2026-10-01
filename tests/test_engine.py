"""
Unit + scenario tests.   Run:  python -m unittest discover -s tests -v
"""
import unittest
from datetime import datetime

from backend.matching import (bayesian_rating, distance_score, haversine_km, language_score,
                              cost_score, availability_score, WEIGHTS)
from backend.nlp import detect_language
from backend.pipeline import MedAssistEngine

NOW = datetime(2026, 10, 2, 10, 5)      # a Friday morning, fixed so tests are repeatable
AMITY = (28.5440, 77.3330)
ENGINE = MedAssistEngine()


def run(text, **kw):
    return ENGINE.analyze(text, *AMITY, now=NOW, **kw)


class TestMatchingMaths(unittest.TestCase):
    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0)

    def test_haversine_known_distance(self):
        # Connaught Place -> Amity Noida is roughly 15 km in a straight line
        km = haversine_km(28.6315, 77.2167, *AMITY)
        self.assertTrue(13 < km < 17, km)
        self.assertAlmostEqual(haversine_km(*AMITY, *AMITY), 0.0)

    def test_distance_score_halves_at_scale(self):
        self.assertAlmostEqual(distance_score(0), 1.0)
        self.assertAlmostEqual(distance_score(5), 0.5)

    def test_bayesian_rating_shrinks_small_samples(self):
        self.assertLess(bayesian_rating(5.0, 2), bayesian_rating(4.6, 300))
        self.assertAlmostEqual(bayesian_rating(4.0, 0), 3.5)

    def test_component_ranges(self):
        self.assertEqual(language_score("hinglish", ["hi"]), 1.0)
        self.assertEqual(language_score("en", ["hi"]), 0.0)
        self.assertEqual(cost_score(0), 1.0)
        self.assertEqual(cost_score(5000), 0.0)
        self.assertEqual(availability_score(None), 0.0)


class TestLanguage(unittest.TestCase):
    def test_detection(self):
        self.assertEqual(detect_language("I have a headache")["code"], "en")
        self.assertEqual(detect_language("मुझे बुखार है")["code"], "hi")
        self.assertEqual(detect_language("mujhe bukhar hai aur sir dard")["code"], "hinglish")
        self.assertEqual(detect_language("எனக்கு காய்ச்சல்")["code"], "ta")


class TestExtraction(unittest.TestCase):
    def test_english_with_duration(self):
        r = run("I have had fever and body ache for 3 days")
        ids = {s["id"] for s in r["symptoms"]}
        self.assertEqual(ids, {"fever", "body_ache"})
        self.assertEqual(r["duration_days"], 3)

    def test_hindi_negation(self):
        r = run("मुझे दो दिन से पेट दर्द और उल्टी हो रही है, बुखार नहीं है")
        self.assertIn("abdominal_pain", {s["id"] for s in r["symptoms"]})
        self.assertIn("fever", {s["id"] for s in r["negated"]})
        self.assertEqual(r["duration_days"], 2)

    def test_hinglish(self):
        r = run("mujhe 3 din se tez bukhar hai, aankhon ke peeche dard aur jodon mein dard")
        self.assertTrue({"high_fever", "fever", "eye_pain", "joint_pain"} <= {s["id"] for s in r["symptoms"]})
        self.assertEqual(r["conditions"][0]["id"], "dengue")

    def test_typo_is_fuzzy_matched(self):
        r = run("vomitting and loose motions since morning")
        self.assertIn("vomiting", {s["id"] for s in r["symptoms"]})

    def test_duration_years_is_not_age(self):
        r = run("headache for 2 years")
        self.assertIsNone(r["age"])
        self.assertEqual(r["duration_days"], 730)

    def test_temperature(self):
        r = run("fever of 103 F with chills")
        self.assertEqual(r["temperature_f"], 103.0)
        self.assertIn("high_fever", {s["id"] for s in r["symptoms"]})


class TestTriage(unittest.TestCase):
    def test_cardiac_red_flag_is_high(self):
        r = run("I have severe chest pain spreading to my left arm and I am sweating")
        self.assertEqual(r["triage"]["level"], "HIGH")
        self.assertTrue(r["triage"]["emergency"])
        self.assertTrue(r["doctors"][0]["emergency"])          # nearest ER pinned first

    def test_stroke_is_high(self):
        self.assertEqual(run("his face is drooping and speech is slurred")["triage"]["level"], "HIGH")

    def test_common_cold_is_low(self):
        r = run("runny nose and sneezing, mild sore throat, no fever")
        self.assertEqual(r["triage"]["level"], "LOW")
        self.assertEqual(r["conditions"][0]["id"], "common_cold")

    def test_unknown_is_uncertain_and_goes_to_gp(self):
        r = run("I feel weird")
        self.assertEqual(r["triage"]["level"], "UNCERTAIN")
        self.assertTrue(all(d["specialty"] == "General Physician" for d in r["doctors"]))

    def test_follow_up_symptom_raises_risk(self):
        before = run("mujhe tez bukhar hai aur jodon mein dard")
        after = run("mujhe tez bukhar hai aur jodon mein dard", extra_symptoms=["bleeding_gums"])
        self.assertEqual(after["triage"]["level"], "HIGH")
        self.assertNotEqual(before["triage"]["level"], "HIGH")

    def test_elderly_scores_higher(self):
        young = run("headache since yesterday")["triage"]["score"]
        old = run("headache since yesterday, I am 67 years old")["triage"]["score"]
        self.assertGreater(old, young)


class TestDoctorMatching(unittest.TestCase):
    def test_specialist_routing(self):
        self.assertEqual(run("itchy red eyes with watery discharge")["doctors"][0]["specialty"], "Ophthalmologist")
        self.assertEqual(run("I can't sleep, feeling anxious and sad")["doctors"][0]["specialty"], "Psychiatrist")

    def test_video_mode_only_teleconsult(self):
        r = ENGINE.analyze("fever and cough", 28.10, 77.58, mode="video", now=NOW)
        self.assertTrue(r["doctors"])
        self.assertTrue(all(d["teleconsult"] for d in r["doctors"]))

    def test_booking_removes_slot(self):
        r = run("fever and cough")
        doc = r["doctors"][0]
        slot = doc["slots"][0]
        booking = ENGINE.scheduler.book(ENGINE.doctor_by_id[doc["id"]], slot, "Test", "in_person", now=NOW)
        self.assertTrue(booking["booking_id"].startswith("MA-"))
        with self.assertRaises(ValueError):
            ENGINE.scheduler.book(ENGINE.doctor_by_id[doc["id"]], slot, "Test", "in_person", now=NOW)


class TestKnowledgeGraph(unittest.TestCase):
    def test_cypher_export(self):
        cy = ENGINE.kg.to_cypher()
        self.assertIn("HAS_SYMPTOM", cy)
        self.assertIn("MERGE (:Condition {id:'dengue'", cy)


if __name__ == "__main__":
    unittest.main()
