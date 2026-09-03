"""Tests for Stages 8-10: high-risk ranking, evidence trail, PDF dossier."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.graph_models import GraphPayload
from app.services.graph_store import engine

FIXTURE = Path(__file__).parent / "fixtures" / "sample_graph.json"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reload_fixture():
    engine.load_graph(GraphPayload.model_validate(json.loads(FIXTURE.read_text())))
    yield
    engine.load_graph(GraphPayload.model_validate(json.loads(FIXTURE.read_text())))


def test_high_risk_ranked_and_shaped() -> None:
    resp = client.get("/api/analytics/high-risk", params={"limit": 5})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 5
    assert [r["rank"] for r in results] == [1, 2, 3, 4, 5]
    scores = [r["betweenness"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["node_id"] == "suspect_arif"
    assert set(results[0]) == {
        "rank", "node_id", "label", "type",
        "betweenness", "pagerank", "community_id",
    }


def test_high_risk_limit_clamped() -> None:
    assert client.get("/api/analytics/high-risk", params={"limit": 100}).status_code == 422


def test_evidence_trail_full_xai() -> None:
    resp = client.get(
        "/api/evidence-trail", params={"source": "phone_p2", "target": "phone_p3"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == {"id": "phone_p2", "label": "+91-98XXXXXX02"}
    assert body["target"]["id"] == "phone_p3"
    assert len(body["relationships"]) == 3  # parallel CALLS preserved
    rel = body["relationships"][0]
    assert rel["type"] == "CALLED"
    assert rel["cdr_id"].startswith("CDR-")
    assert set(rel) == {
        "edge_id", "type", "timestamp", "amount", "duration",
        "transaction_id", "cdr_id", "fir_id", "fir_excerpt", "source_document",
    }


def test_evidence_trail_404_cases() -> None:
    assert client.get(
        "/api/evidence-trail", params={"source": "phone_p1", "target": "acct_arif"}
    ).status_code == 404
    assert client.get(
        "/api/evidence-trail", params={"source": "ghost", "target": "phone_p1"}
    ).status_code == 404


def test_export_dossier_pdf() -> None:
    resp = client.get("/api/export-dossier")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "investigative_dossier.pdf" in resp.headers["content-disposition"]
    assert resp.content[:4] == b"%PDF"
    assert len(resp.content) > 1000


def test_ingest_reloads_engine() -> None:
    payload = {
        "nodes": [{"id": "s1", "type": "Suspect", "label": "Solo"}],
        "edges": [],
    }
    resp = client.post("/api/ingest", json=payload)
    assert resp.status_code == 200
    assert resp.json()["stats"]["total_nodes"] == 1
    assert client.get("/api/graph").json()["elements"]["nodes"][0]["data"]["id"] == "s1"
