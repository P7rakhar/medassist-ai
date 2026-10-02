"""
Data-driven second opinion: a logistic-regression model trained on 1,200 public patient descriptions
(Symptom2Disease, 24 diseases). Training: training/train_model.py (scikit-learn); this file only runs
the exported weights, in pure Python, so the app still needs nothing beyond FastAPI.

Features
  sym:<id>   the symptom codes our own NLP extracts (works for English, Hindi and Hinglish alike)
  w:<word>   English words in the description (adds detail for English text only)

The knowledge graph and the NHS warning-sign rules stay in charge of triage. The model only offers a
second ranking of likely diseases; when it disagrees with the knowledge graph the note says so, so a
doctor looks at both.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

MODEL_PATH = Path(__file__).parent / "data" / "model_symptom2disease.json"
STOP = set("""the and for with have has had been being this that there their they them then than are was were will would
could should can cant also very really just some any all not but from into onto over under about after before because
while when what which who whom whose where how why its it's i'm ive i've my me myself our you your yours his her hers him
she he we us ourselves feel feeling felt lot lots little bit much more most such even still too get got getting gets
make makes made like it's been day days week weeks time times sometimes often always usually recently lately past""".split())
_WORD = re.compile(r"[a-z]{3,}")
CONFIDENT = 0.35        # below this the model's top answer is shown as "not confident", not as a disagreement


def tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in STOP}


def features(text: str, symptom_weights: dict[str, float]) -> dict[str, float]:
    f = {f"sym:{s}": float(w) for s, w in symptom_weights.items()}
    f.update({f"w:{t}": 1.0 for t in tokens(text)})
    return f


class SecondOpinion:
    def __init__(self, path: Path = MODEL_PATH):
        self.ok = path.exists()
        if not self.ok:
            return
        m = json.loads(path.read_text(encoding="utf-8"))
        self.labels: list[str] = m["labels"]
        self.kg_map: dict[str, str | None] = m["kg_map"]
        self.intercept: list[float] = m["intercept"]
        self.coef: dict[str, list[float]] = m["coef"]          # feature -> one weight per label
        # Symptom-codes-only variant: used when the text has no English words the full model knows.
        self.intercept_codes: list[float] = m.get("intercept_codes", self.intercept)
        self.coef_codes: dict[str, list[float]] = m.get("coef_codes", {})
        self.metrics: dict = m["metrics"]
        self.dataset: dict = m["dataset"]

    def predict(self, text: str, symptom_weights: dict[str, float], kg_top: list[str], label_of=None) -> dict | None:
        if not self.ok:
            return None
        allf = features(text, symptom_weights)
        words = any(k.startswith("w:") and k in self.coef for k in allf)
        coef, intercept = (self.coef, self.intercept) if words or not self.coef_codes else (self.coef_codes, self.intercept_codes)
        f = {k: v for k, v in allf.items() if k in coef}
        if not f:
            return {"available": False, "reason": "no_features"}
        z = list(intercept)
        for k, v in f.items():
            for i, w in enumerate(coef[k]):
                z[i] += w * v
        mx = max(z)
        e = [math.exp(x - mx) for x in z]
        tot = sum(e)
        p = [x / tot for x in e]
        order = sorted(range(len(p)), key=lambda i: -p[i])[:3]
        best = order[0]
        why = sorted(((k, coef[k][best] * v) for k, v in f.items() if k.startswith("sym:")), key=lambda x: -x[1])
        kg_id = self.kg_map.get(self.labels[best])
        return {
            "available": True,
            "top": [{"label": self.labels[i], "probability": round(p[i], 3), "kg_id": self.kg_map.get(self.labels[i])} for i in order],
            "because": [k[4:] for k, w in why[:3] if w > 0],
            "confident": p[best] >= CONFIDENT,
            "agrees": None if kg_id is None or p[best] < CONFIDENT else kg_id in kg_top,
            "in_kg": kg_id is not None,
            "used_words": words,
            "model": {"name": "Logistic regression", "dataset": self.dataset["name"], "cases": self.dataset["cases"],
                      "diseases": len(self.labels), "held_out_accuracy": self.metrics["held_out"]["accuracy"]},
        }
