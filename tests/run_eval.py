"""
Measure MedAssist AI on 60 team-written patient descriptions.

    python tests/run_eval.py            (summary + comparison with simpler systems + failures)
    python tests/run_eval.py --json     (machine-readable)

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
        out = {**res, "comparison": {name: {"general": {k: v for k, v in g.items() if k != "rows"},
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
