"""
Medical knowledge graph.

Graph schema (property graph, Neo4j-compatible):
    (:Condition)-[:HAS_SYMPTOM {weight}]->(:Symptom)
    (:Condition)-[:TREATED_BY]->(:Specialty)
    (:RedFlag)-[:TRIGGERED_BY {all_of | any_of}]->(:Symptom)

For the prototype the graph is held in memory (loaded from JSON) so it runs
offline on a laptop or phone. `to_cypher()` exports the same graph to Neo4j
Cypher statements for the production deployment.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


CANDIDATE_POOL = 8


@dataclass
class ConditionMatch:
    id: str
    name: dict
    specialty: str
    severity: float
    coverage: float        # share of the condition's symptom profile that the patient has (weighted)
    explained: float       # share of the patient's symptoms that this condition explains
    raw: float             # combined score before normalisation
    likelihood: float      # normalised across candidate conditions (sums to 1)
    matched: list[str]
    ask_about: list[str]   # most informative missing symptoms -> follow-up questions
    advice: dict
    icd10: str | None = None
    info_source: str | None = None


class KnowledgeGraph:
    def __init__(self, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.version = data.get("version", "dev")
        self.symptoms: dict = data["symptoms"]
        self.conditions: dict = data["conditions"]
        self.specialties: dict = data["specialties"]
        self.red_flag_rules: list = data["red_flags"]
        self.risk_factors: dict = data.get("risk_factors", {})
        self.mentioned_conditions: dict = data.get("mentioned_conditions", {})
        self._validate()
        self.specialty_vectors = {name: self._specialty_vector(name) for name in self.specialties}

    # ------------------------------------------------------------ helpers ---
    def _validate(self) -> None:
        """Fail fast if the graph references a symptom or condition that doesn't exist."""
        for cid, c in self.conditions.items():
            for sid in c["symptoms"]:
                assert sid in self.symptoms, f"{cid} references unknown symptom {sid}"
            assert c["specialty"] in self.specialties, f"{cid} has unknown specialty"
        for spec, s in self.specialties.items():
            for cid in s["treats"]:
                assert cid in self.conditions, f"{spec} treats unknown condition {cid}"
        for rule in self.red_flag_rules:
            for sid in rule["all_of"] + rule["any_of"]:
                assert sid in self.symptoms, f"red flag {rule['id']} uses unknown symptom {sid}"
            assert rule.get("requires_risk") in (None, *self.risk_factors), f"red flag {rule['id']} uses unknown risk"

    def label(self, symptom_id: str, lang: str = "en") -> str:
        lab = self.symptoms[symptom_id]["label"]
        return lab.get("hi" if lang in ("hi", "hinglish") else "en", lab["en"])

    def stats(self) -> dict:
        edges = sum(len(c["symptoms"]) for c in self.conditions.values())
        synonyms = sum(len(s.get(k, [])) for s in self.symptoms.values() for k in ("en", "hi", "hinglish"))
        return {"symptoms": len(self.symptoms), "conditions": len(self.conditions),
                "specialties": len(self.specialties), "edges": edges, "synonyms": synonyms,
                "red_flag_rules": len(self.red_flag_rules), "risk_factors": len(self.risk_factors),
                "version": self.version}

    def _specialty_vector(self, specialty: str) -> dict[str, float]:
        """Doctor-expertise vector: sum of symptom weights of every condition the specialty treats."""
        vec: dict[str, float] = {}
        for cid in self.specialties[specialty]["treats"]:
            for sid, w in self.conditions[cid]["symptoms"].items():
                vec[sid] = vec.get(sid, 0.0) + w
        return vec

    def specialty_match(self, patient_vec: dict[str, float], specialty: str) -> float:
        """
        Cosine similarity between the patient's symptom vector and the doctor's expertise.
        Expertise is represented per condition the specialty treats and we take the best
        match, so a broad specialty (General Physician treats 13 conditions) is not diluted
        compared with a narrow one (Ophthalmologist treats 1).
        """
        return max((cosine(patient_vec, self.conditions[cid]["symptoms"])
                    for cid in self.specialties[specialty]["treats"]), default=0.0)

    # -------------------------------------------------------------- query ---
    def query(self, present: list[str] | dict[str, float], absent: list[str] | None = None,
              top_k: int | None = 3) -> list[ConditionMatch]:
        """
        Score every condition against the patient's symptoms.

        `present` is a list of symptom IDs, or {symptom_id: certainty} where an uncertain
        symptom ("maybe fever") counts 0.5.

        coverage  = sum(edge weight x certainty of matched symptoms) / sum(all symptom weights of the condition)
        explained = sum(certainty of matched symptoms) / sum(certainty of all patient symptoms)
        raw       = prevalence * (0.65 * coverage + 0.35 * explained) * negation_penalty
        likelihood = raw / sum(raw of the 8 best)   (relative, not a clinical probability)
        """
        pw = present if isinstance(present, dict) else {s: 1.0 for s in present}
        absent_set = set(absent or [])
        if not pw:
            return []
        total_pw = sum(pw.values())
        results = []
        for cid, weights in self._candidate_edges(pw):
            c = self.conditions[cid]
            matched = [s for s in weights if s in pw]
            if not matched:
                continue
            total_w = sum(weights.values())
            coverage = sum(weights[s] * pw[s] for s in matched) / total_w
            explained = sum(pw[s] for s in matched) / total_pw
            # A denied key symptom ("no fever") makes the condition less likely.
            denied_w = sum(weights[s] for s in weights if s in absent_set)
            penalty = 1.0 - 0.5 * (denied_w / total_w)
            raw = c.get("prevalence", 1.0) * (0.65 * coverage + 0.35 * explained) * penalty
            missing = sorted((s for s in weights if s not in pw and s not in absent_set),
                             key=lambda s: -weights[s])
            results.append(ConditionMatch(
                id=cid, name=c["name"], specialty=c["specialty"], severity=c["severity"],
                coverage=round(coverage, 3), explained=round(explained, 3), raw=raw, likelihood=0.0,
                matched=matched, ask_about=missing[:3], advice=c["advice"],
                icd10=c.get("icd10"), info_source=c.get("info_source"),
            ))
        # Likelihood is relative among the 8 strongest candidates, so a long tail of conditions that
        # share one weak symptom doesn't dilute the picture.
        results.sort(key=lambda r: -r.raw)
        total = sum(r.raw for r in results[:CANDIDATE_POOL]) or 1.0
        for r in results:
            r.likelihood = round(r.raw / total, 3)
        return results[:top_k] if top_k else results

    def _candidate_edges(self, pw: dict[str, float]):
        """(condition_id, {symptom_id: weight}) for every condition sharing a symptom with the patient.
        The Neo4j backend (graph_neo4j.py) overrides this with a Cypher query."""
        for cid, c in self.conditions.items():
            if any(s in pw for s in c["symptoms"]):
                yield cid, c["symptoms"]

    def red_flags(self, present: list[str], risks: list[str] | None = None) -> list[dict]:
        s, r = set(present), set(risks or [])
        fired = []
        for rule in self.red_flag_rules:
            if rule.get("requires_risk") and rule["requires_risk"] not in r:
                continue
            if all(x in s for x in rule["all_of"]) and (not rule["any_of"] or any(x in s for x in rule["any_of"])):
                fired.append({"id": rule["id"], "message": rule["message"],
                              "triggered_by": [x for x in rule["all_of"] + rule["any_of"] if x in s]})
        return fired

    # ------------------------------------------------------------- export ---
    def to_cypher(self) -> str:
        """Export to Neo4j Cypher (production graph store)."""
        def q(s: str) -> str:
            return s.replace("\\", "\\\\").replace("'", "\\'")
        lines = []
        for sid, s in self.symptoms.items():
            lines.append(f"MERGE (:Symptom {{id:'{sid}', name:'{q(s['label']['en'])}', name_hi:'{q(s['label']['hi'])}'}});")
        for spec in self.specialties:
            lines.append(f"MERGE (:Specialty {{name:'{q(spec)}'}});")
        for cid, c in self.conditions.items():
            lines.append(f"MERGE (:Condition {{id:'{cid}', name:'{q(c['name']['en'])}', severity:{c['severity']}, "
                         f"icd10:'{q(c.get('icd10') or '')}'}});")
            lines.append(f"MATCH (c:Condition {{id:'{cid}'}}), (p:Specialty {{name:'{q(c['specialty'])}'}}) MERGE (c)-[:TREATED_BY]->(p);")
            for sid, w in c["symptoms"].items():
                lines.append(f"MATCH (c:Condition {{id:'{cid}'}}), (s:Symptom {{id:'{sid}'}}) MERGE (c)-[:HAS_SYMPTOM {{weight:{w}}}]->(s);")
        return "\n".join(lines)


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0
