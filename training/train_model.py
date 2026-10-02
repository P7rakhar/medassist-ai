"""
Train MedAssist's data-driven second-opinion model.

    pip install -r requirements-train.txt
    python training/train_model.py --csv path/to/Symptom2Disease.csv

Data: Symptom2Disease (Kaggle, niyarrbarman/symptom2disease): 1,200 English patient descriptions,
50 for each of 24 diseases. Download it yourself from Kaggle (login needed); it is not shipped here.

Method
  1. Every description goes through MedAssist's own NLP, giving symptom codes (sym:fever ...),
     plus English word features (w:itchy ...). Symptom codes are language-independent, so the model
     also works on Hindi and Hinglish input (with codes only).
  2. Multinomial logistic regression (scikit-learn), regularisation strength chosen by 5-fold CV.
  3. Honest evaluation: a stratified 20% held-out split never used for training or tuning, 5-fold CV,
     a symptom-codes-only model for comparison, and a cross-language check on our own 60 cases.
  4. The final model is refit on all 1,200 descriptions and exported as plain JSON weights
     (backend/data/model_symptom2disease.json); the app runs it without scikit-learn.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.model import features  # noqa: E402
from backend.pipeline import MedAssistEngine  # noqa: E402

# Symptom2Disease label -> MedAssist knowledge-graph condition (None = not in our graph).
KG_MAP = {
    "Typhoid": "typhoid", "Chicken pox": "chickenpox", "Dengue": "dengue", "Common Cold": "common_cold",
    "Pneumonia": "pneumonia", "Bronchial Asthma": "asthma", "Hypertension": "hypertension", "Migraine": "migraine",
    "Jaundice": "viral_hepatitis", "Malaria": "malaria", "urinary tract infection": "uti",
    "gastroesophageal reflux disease": "gastritis_gerd", "peptic ulcer disease": "gastritis_gerd", "diabetes": "diabetes",
    "allergy": None, "Cervical spondylosis": None, "Psoriasis": None, "Varicose Veins": None, "Impetigo": None,
    "Fungal infection": None, "Dimorphic Hemorrhoids": None, "Arthritis": None, "Acne": None, "drug reaction": None,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default=str(ROOT / "backend" / "data" / "model_symptom2disease.json"))
    args = ap.parse_args()

    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, f1_score, top_k_accuracy_score
    from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score, train_test_split

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8")))
    engine = MedAssistEngine()
    texts = [r["text"] for r in rows]
    y = [r["label"] for r in rows]
    sym = [engine.extractor.extract(t).weights for t in texts]
    X_full = [features(t, s) for t, s in zip(texts, sym)]
    X_codes = [{k: v for k, v in f.items() if k.startswith("sym:")} for f in X_full]
    labels = sorted(set(y))
    print(f"{len(rows)} descriptions, {len(labels)} diseases; {sum(1 for s in sym if s)} have at least one symptom code")

    idx = list(range(len(rows)))
    tr, te = train_test_split(idx, test_size=0.2, stratify=y, random_state=42)
    cv = StratifiedKFold(5, shuffle=True, random_state=42)

    def fit_eval(X, name):
        vec = DictVectorizer()
        Xtr = vec.fit_transform([X[i] for i in tr]); Xte = vec.transform([X[i] for i in te])
        ytr = [y[i] for i in tr]; yte = [y[i] for i in te]
        grid = GridSearchCV(LogisticRegression(max_iter=3000), {"C": [0.3, 1.0, 3.0, 10.0]}, cv=cv, scoring="accuracy")
        grid.fit(Xtr, ytr)
        clf = grid.best_estimator_
        proba = clf.predict_proba(Xte)
        pred = clf.predict(Xte)
        res = {"accuracy": round(accuracy_score(yte, pred), 3),
               "top3": round(top_k_accuracy_score(yte, proba, k=3, labels=clf.classes_), 3),
               "macro_f1": round(f1_score(yte, pred, average="macro"), 3), "C": grid.best_params_["C"],
               "test_cases": len(te)}
        per = Counter(); tot = Counter()
        for t, p in zip(yte, pred):
            tot[t] += 1; per[t] += t == p
        res["per_disease_recall"] = {k: round(per[k] / tot[k], 2) for k in sorted(tot)}
        print(f"{name}: held-out accuracy {res['accuracy']:.1%}, top-3 {res['top3']:.1%}, macro-F1 {res['macro_f1']:.3f} (C={res['C']})")
        return res, grid.best_params_["C"]

    held_full, C_full = fit_eval(X_full, "Symptom codes + words")
    held_codes, C_codes = fit_eval(X_codes, "Symptom codes only    ")

    vec = DictVectorizer()
    Xall = vec.fit_transform(X_full)
    cv_scores = cross_val_score(LogisticRegression(max_iter=3000, C=C_full), Xall, y, cv=cv)
    print(f"5-fold cross-validation (all 1,200): {cv_scores.mean():.1%} ± {cv_scores.std():.1%}")

    # Final model: refit on everything with the chosen C, export weights.
    final = LogisticRegression(max_iter=3000, C=C_full).fit(Xall, y)
    names = vec.get_feature_names_out()
    coef = {}
    for j, name in enumerate(names):
        col = [round(float(final.coef_[i][j]), 4) for i in range(len(final.classes_))]
        if max(abs(w) for w in col) >= 0.01:
            coef[name] = col

    # Codes-only model, used when the text has no English words the full model knows (Hindi, Hinglish).
    vec_c = DictVectorizer()
    final_c = LogisticRegression(max_iter=3000, C=C_codes).fit(vec_c.fit_transform(X_codes), y)
    assert list(final_c.classes_) == list(final.classes_)
    coef_c = {name: [round(float(final_c.coef_[i][j]), 4) for i in range(len(final_c.classes_))]
              for j, name in enumerate(vec_c.get_feature_names_out())}

    # Cross-language check on our own 60 cases (English, Hindi, Hinglish) with a mappable expected condition.
    inv = {}
    for lab, kg in KG_MAP.items():
        if kg:
            inv.setdefault(kg, []).append(lab)
    cases = json.loads((ROOT / "tests" / "eval_cases.json").read_text(encoding="utf-8"))["cases"]
    from backend.model import SecondOpinion
    tmp = Path(args.out).with_suffix(".tmp.json")
    model = {"version": "1", "trained_at": date.today().isoformat(), "labels": [str(c) for c in final.classes_],
             "kg_map": {lab: KG_MAP.get(lab) for lab in final.classes_}, "intercept": [round(float(b), 4) for b in final.intercept_],
             "coef": coef, "intercept_codes": [round(float(b), 4) for b in final_c.intercept_], "coef_codes": coef_c,
             "dataset": {"name": "Symptom2Disease (Kaggle: niyarrbarman/symptom2disease)", "cases": len(rows), "diseases": len(labels)},
             "metrics": {"held_out": held_full, "held_out_codes_only": held_codes,
                         "cv5_accuracy": {"mean": round(float(cv_scores.mean()), 3), "sd": round(float(cv_scores.std()), 3)}}}
    tmp.write_text(json.dumps(model), encoding="utf-8")
    so = SecondOpinion(tmp)
    by_lang = Counter(); hit1 = Counter(); hit3 = Counter()
    for c in cases:
        if not c["condition"] or c["condition"] not in inv:
            continue
        r = engine.analyze(c["text"], 28.544, 77.333, log_case=False)
        out = so.predict(c["text"], {s["id"]: (0.5 if s["uncertain"] else 1.0) for s in r["symptoms"]}, [])
        by_lang[c["lang"]] += 1
        if out and out.get("available"):
            top = [t["label"] for t in out["top"]]
            hit1[c["lang"]] += top[0] in inv[c["condition"]]
            hit3[c["lang"]] += any(t in inv[c["condition"]] for t in top)
    cross = {lang: {"cases": n, "top1": hit1[lang], "top3": hit3[lang]} for lang, n in sorted(by_lang.items())}
    print("Cross-language check on our own cases (expected disease is one the model knows):")
    for lang, v in cross.items():
        print(f"  {lang:9s} {v['cases']:2d} cases: top-1 {v['top1']}, top-3 {v['top3']}")
    model["metrics"]["cross_language_own_cases"] = cross
    tmp.unlink()
    Path(args.out).write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Saved {args.out}: {len(coef)} features x {len(final.classes_)} diseases")


if __name__ == "__main__":
    main()
