"""
Measure MedAssist AI on 60 team-written patient descriptions.

    python tests/run_eval.py            (summary + comparison with simpler systems + failures)
    python tests/run_eval.py --json     (machine-readable)
    python tests/run_eval.py --db medassist.db   (also: doctor-labelled cases collected in the doctor view)

Metrics
  triage accuracy     predicted level is one of the acceptable levels
  under-triage        a true emergency (only HIGH acceptable) rated lower  <- the safety metric
  over-triage         rated HIGH when HIGH was not acceptable
  top-1 / top-3       expected condition is the first / among the first three shown

Comparison (tests/baselines.py): the same cases through plain keyword matching, and through
MedAssist with its ConText (negation / uncertainty / history) step switched off.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.pipeline import MedAssistEngine  # noqa: E402
from tests.baselines import keyword_engine, no_context_engine  # noqa: E402

CASES = json.loads((Path(__file__).parent / "eval_cases.json").read_text(encoding="utf-8"))["cases"]
CONTEXT_CASES = json.loads((Path(__file__).parent / "context_cases.json").read_text(encoding="utf-8"))["cases"]
# Independent benchmark: 45 cases written and triage-labelled by physicians (Semigran et al., BMJ 2015).
DOCTOR_CASES = json.loads((Path(__file__).parent / "doctor_vignettes.json").read_text(encoding="utf-8"))["cases"]
RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2}
# Recorded once, so the improvement stays visible: v0.5 (before the NHS warning-sign rules) on the same 45 cases.
DOCTOR_BEFORE = {"version": "0.5", "correct": 18, "emergencies_high": 4, "cases": 45}
# Published reference points on the same 45 vignettes.
DOCTOR_REFERENCE = [("23 symptom-checker apps (Semigran et al., BMJ 2015)", "57%", "80%")]
NOW = datetime(2026, 10, 2, 10, 5)


def evaluate(engine: MedAssistEngine) -> dict:
    rows = []
    for c in CASES:
        r = engine.analyze(c["text"], 28.5440, 77.3330, now=NOW, log_case=False)
        level = r["triage"]["level"]
        # top-3 = the three best-ranked conditions (the UI may show fewer if the others are far behind)
        weights = {s["id"]: 0.5 if s["uncertain"] else 1.0 for s in r["symptoms"]}
        absent = [s["id"] for s in r["negated"]]
        top3 = [m.id for m in engine.kg.query(weights, absent, top_k=3)]
        rows.append({
            "id": c["id"], "lang": c["lang"], "text": c["text"], "expected_levels": c["levels"], "level": level,
            "level_ok": level in c["levels"],
            "under_triage": c["levels"] == ["HIGH"] and level != "HIGH",
            "over_triage": level == "HIGH" and "HIGH" not in c["levels"],
            "expected_condition": c["condition"], "top": top3[:3],
            "top1": c["condition"] is None or (top3[:1] == [c["condition"]]),
            "top3": c["condition"] is None or c["condition"] in top3[:3],
            "symptoms": [s["id"] for s in r["symptoms"]], "ms": r["total_ms"],
        })
    n = len(rows)
    with_cond = [x for x in rows if x["expected_condition"]]
    emergencies = [x for x in rows if x["expected_levels"] == ["HIGH"]]
    by_lang = defaultdict(lambda: [0, 0])
    for x in rows:
        by_lang[x["lang"]][0] += x["level_ok"]; by_lang[x["lang"]][1] += 1
    return {
        "cases": n,
        "triage_accuracy": round(sum(x["level_ok"] for x in rows) / n, 3),
        "emergencies": len(emergencies),
        "under_triage": sum(x["under_triage"] for x in rows),
        "over_triage": sum(x["over_triage"] for x in rows),
        "condition_cases": len(with_cond),
        "top1_accuracy": round(sum(x["top1"] for x in with_cond) / len(with_cond), 3),
        "top3_accuracy": round(sum(x["top3"] for x in with_cond) / len(with_cond), 3),
        "triage_accuracy_by_language": {k: f"{a}/{b}" for k, (a, b) in by_lang.items()},
        "mean_ms": round(sum(x["ms"] for x in rows) / n, 1),
        "rows": rows,
    }


def evaluate_context(engine: MedAssistEngine) -> dict:
    """Negation / past-history set: is a symptom the patient said they DON'T have kept out?"""
    rows = []
    for c in CONTEXT_CASES:
        r = engine.analyze(c["text"], 28.5440, 77.3330, now=NOW, log_case=False)
        found = {s["id"] for s in r["symptoms"]}
        level = r["triage"]["level"]
        rows.append({"id": c["id"], "text": c["text"], "level": level, "level_ok": level in c["levels"],
                     "over_triage": level == "HIGH" and "HIGH" not in c["levels"],
                     "under_triage": c["levels"] == ["HIGH"] and level != "HIGH",
                     "wrongly_counted": [s for s in c["not_present"] if s in found],
                     "missed": [s for s in c["present"] if s not in found]})
    return {"cases": len(rows), "denied_total": sum(len(c["not_present"]) for c in CONTEXT_CASES),
            "wrongly_counted": sum(len(x["wrongly_counted"]) for x in rows),
            "missed": sum(len(x["missed"]) for x in rows),
            "triage_ok": sum(x["level_ok"] for x in rows), "over_triage": sum(x["over_triage"] for x in rows),
            "under_triage": sum(x["under_triage"] for x in rows), "rows": rows}


def evaluate_doctor(engine: MedAssistEngine) -> dict:
    """The physician-labelled benchmark. UNCERTAIN counts as wrong (it is a referral, not a triage level)."""
    rows = []
    for c in DOCTOR_CASES:
        r = engine.analyze(c["text"], 28.5440, 77.3330, now=NOW, log_case=False)
        level = r["triage"]["level"]
        rank = RANK.get(level)
        want = RANK[c["expected_level"]]
        rows.append({"id": c["id"], "urgency": c["urgency"], "expected": c["expected_level"], "level": level,
                     "diagnosis": c["diagnosis"], "correct": level == c["expected_level"],
                     "under": rank is not None and rank < want, "over": rank is not None and rank > want,
                     "symptoms": [s["id"] for s in r["symptoms"]]})
    by = lambda u: [x for x in rows if x["urgency"] == u]
    return {"cases": len(rows), "correct": sum(x["correct"] for x in rows),
            "emergency_high": sum(x["level"] == "HIGH" for x in by("em")), "emergencies": len(by("em")),
            "by_level": {u: f"{sum(x['correct'] for x in by(u))}/{len(by(u))}" for u in ("em", "ne", "sc")},
            "under": sum(x["under"] for x in rows), "over": sum(x["over"] for x in rows),
            "uncertain": sum(x["level"] == "UNCERTAIN" for x in rows), "rows": rows}


def evaluate_labelled(engine: MedAssistEngine, db_path: str) -> dict:
    """Re-run the current engine on doctor-labelled cases from real use (doctor view -> "Your assessment")."""
    from backend.db import Store
    from backend.labels import agreement, labelled_cases
    store = Store(db_path)
    try:
        cases = labelled_cases(store.bookings())
    finally:
        store.close()
    for c in cases:
        c["now_level"] = engine.analyze(c["patient_words"], 28.5440, 77.3330, now=NOW, log_case=False)["triage"]["level"]
    return {"at_booking": agreement(cases), "now": agreement(cases, "now_level"), "cases": cases}


def compare() -> list[tuple[str, dict, dict]]:
    out = []
    for name, make in [("Keyword matching (typical checker)", keyword_engine),
                       ("MedAssist without ConText", no_context_engine),
                       ("MedAssist AI (full)", MedAssistEngine)]:
        eng = make()
        out.append((name, evaluate(eng), evaluate_context(eng)))
    return out


def main():
    res = evaluate(MedAssistEngine())
    if "--json" in sys.argv:
        out = {**res, "doctor_benchmark": {k: v for k, v in evaluate_doctor(MedAssistEngine()).items() if k != "rows"},
               "comparison": {name: {"general": {k: v for k, v in g.items() if k != "rows"},
                                            "negation": {k: v for k, v in n.items() if k != "rows"}}
                                     for name, g, n in compare()}}
        print(json.dumps(out, ensure_ascii=False, indent=1)); return
    print(f"Cases: {res['cases']}  (EN/HI/Hinglish: {res['triage_accuracy_by_language']})")
    print(f"Triage accuracy:  {res['triage_accuracy']:.0%}")
    print(f"Under-triage:     {res['under_triage']} of {res['emergencies']} emergencies")
    print(f"Over-triage:      {res['over_triage']}")
    print(f"Top-1 condition:  {res['top1_accuracy']:.0%}   Top-3: {res['top3_accuracy']:.0%}  (of {res['condition_cases']})")
    print(f"Mean time:        {res['mean_ms']} ms per case")
    results = compare()
    print("\nCompared with simpler systems (same knowledge graph and triage rules; only the language understanding differs)")
    print(f"\nA) The 60 general cases")
    print(f"  {'System':<36}{'Triage OK':>10}{'Under-triage':>14}{'Over-triage':>13}{'Top-1':>7}{'Top-3':>7}")
    for name, r, _ in results:
        print(f"  {name:<36}{r['triage_accuracy']:>10.0%}{str(r['under_triage']) + ' of ' + str(r['emergencies']):>14}"
              f"{r['over_triage']:>13}{r['top1_accuracy']:>7.0%}{r['top3_accuracy']:>7.0%}")
    n0 = results[0][2]
    print(f"\nB) {n0['cases']} negation / past-history cases, e.g. \"no chest pain, just acidity\" ({n0['denied_total']} denied or past symptoms)")
    print(f"  {'System':<36}{'Denied symptoms counted':>24}{'Triage OK':>11}{'Over-triage':>13}")
    for name, _, r in results:
        print(f"  {name:<36}{str(r['wrongly_counted']) + ' of ' + str(r['denied_total']):>24}"
              f"{str(r['triage_ok']) + '/' + str(r['cases']):>11}{r['over_triage']:>13}")
    d = evaluate_doctor(MedAssistEngine())
    b = DOCTOR_BEFORE
    print(f"\nC) Independent benchmark: {d['cases']} cases written and triage-labelled by physicians (Semigran et al., BMJ 2015)")
    print(f"  {'System':<52}{'Correct triage':>16}{'Emergencies -> HIGH':>21}")
    print(f"  {'MedAssist v' + b['version'] + ' (before NHS warning-sign rules)':<52}"
          f"{str(b['correct']) + '/' + str(b['cases']) + ' (' + format(b['correct'] / b['cases'], '.0%') + ')':>16}"
          f"{str(b['emergencies_high']) + '/15':>21}")
    print(f"  {'MedAssist AI now':<52}{str(d['correct']) + '/' + str(d['cases']) + ' (' + format(d['correct'] / d['cases'], '.0%') + ')':>16}"
          f"{str(d['emergency_high']) + '/' + str(d['emergencies']):>21}")
    for name, acc, em in DOCTOR_REFERENCE:
        print(f"  {name:<52}{acc:>16}{em:>21}")
    print(f"  Now: emergency {d['by_level']['em']}, see-a-doctor {d['by_level']['ne']}, self-care {d['by_level']['sc']}; "
          f"under-triaged {d['under']}, over-triaged {d['over']}, sent to a doctor as UNCERTAIN {d['uncertain']}.")
    print("  Honest note: the warning-sign rules were added after seeing the v0.5 misses, so 'now' is no longer a blind test.")
    for x in d["rows"]:
        if x["urgency"] == "em" and x["level"] != "HIGH":
            print(f"  emergency missed {x['id']}: {x['diagnosis']} -> {x['level']}")

    if "--db" in sys.argv:
        path = sys.argv[sys.argv.index("--db") + 1]
        lab = evaluate_labelled(MedAssistEngine(), path)
        a, n = lab["at_booking"], lab["now"]
        print(f"\nD) Doctor-labelled cases from real use ({path}): {a['cases']}")
        if a["cases"]:
            print(f"  AI agreed with the doctor: {a['agree']}/{a['cases']} when booked, {n['agree']}/{n['cases']} with today's engine; "
                  f"AI lower than the doctor: {a['ai_lower_than_doctor']} -> {n['ai_lower_than_doctor']}")

    full_ctx = results[-1][2]
    for x in full_ctx["rows"]:
        if x["wrongly_counted"] or x["missed"] or not x["level_ok"]:
            print(f"  miss {x['id']}: level {x['level']}, counted {x['wrongly_counted']}, missed {x['missed']} — {x['text']}")
    misses = [x for x in res["rows"] if not (x["level_ok"] and x["top3"])]
    if misses:
        print("\nMisses:")
        for x in misses:
            print(f"  {x['id']}: level {x['level']} (want {'/'.join(x['expected_levels'])}), "
                  f"top {x['top']} (want {x['expected_condition']}), saw {x['symptoms']}  — {x['text']}")


if __name__ == "__main__":
    main()
