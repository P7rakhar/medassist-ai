"""
OPTIONAL Neo4j graph backend (off by default).

When NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD are set (for example a free Neo4j
AuraDB instance) and the `neo4j` driver is installed (requirements-optional.txt):

  1. On start-up the knowledge graph is written to Neo4j with idempotent MERGE
     statements (the same export as /api/knowledge-graph/cypher).
  2. For every analysis, candidate conditions are retrieved with a Cypher graph
     query: conditions connected to any of the patient's symptoms, with all of
     their HAS_SYMPTOM edges and weights.
  3. Scoring, triage and red flags then run exactly as in memory, so results are
     identical; only where the graph lives changes.

If anything fails (driver missing, wrong password, network down) the app logs the
reason and keeps using the in-memory graph, so the demo can never break.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("medassist.neo4j")

CANDIDATES_CYPHER = """
MATCH (c:Condition)-[:HAS_SYMPTOM]->(s:Symptom)
WHERE s.id IN $present
WITH DISTINCT c
MATCH (c)-[r:HAS_SYMPTOM]->(s2:Symptom)
RETURN c.id AS id, collect([s2.id, r.weight]) AS edges
"""


def connect_if_configured(engine) -> dict:
    uri = os.environ.get("NEO4J_URI")
    if not uri:
        return {"backend": "in-memory", "detail": "Set NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD to use Neo4j."}
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return {"backend": "in-memory", "detail": "neo4j driver not installed: pip install -r requirements-optional.txt"}
    try:
        driver = GraphDatabase.driver(uri, auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "")))
        driver.verify_connectivity()
        statements = [s for s in engine.kg.to_cypher().split("\n") if s.strip()]
        with driver.session() as session:
            session.run("CREATE CONSTRAINT symptom_id IF NOT EXISTS FOR (s:Symptom) REQUIRE s.id IS UNIQUE").consume()
            session.run("CREATE CONSTRAINT condition_id IF NOT EXISTS FOR (c:Condition) REQUIRE c.id IS UNIQUE").consume()
            session.execute_write(lambda tx: [tx.run(st).consume() for st in statements])
        _attach(engine.kg, driver)
        engine.graph_backend = "neo4j"
        return {"backend": "neo4j", "uri": uri, "statements_synced": len(statements)}
    except Exception as exc:  # noqa: BLE001 — any failure falls back to memory
        log.warning("Neo4j unavailable, using in-memory graph: %s", exc)
        return {"backend": "in-memory", "detail": f"Neo4j connection failed ({type(exc).__name__}); using in-memory graph."}


def _attach(kg, driver) -> None:
    """Replace the knowledge graph's candidate retrieval with a Cypher query (memory fallback on error)."""
    memory_candidates = kg._candidate_edges

    def neo4j_candidates(pw: dict[str, float]):
        try:
            with driver.session() as session:
                rows = session.run(CANDIDATES_CYPHER, present=list(pw)).data()
            return [(r["id"], {sid: w for sid, w in r["edges"]}) for r in rows if r["id"] in kg.conditions]
        except Exception as exc:  # noqa: BLE001
            log.warning("Neo4j query failed, falling back to memory: %s", exc)
            return list(memory_candidates(pw))

    kg._candidate_edges = neo4j_candidates
