"""Tests for Stages 6 & 7: temporal filtering + Cytoscape API."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.graph import engine
from app.main import app
from app.models.graph_models import GraphPayload

FIXTURE = Path(__file__).parent / "fixtures" / "sample_graph.json"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reload_fixture():
    engine.load_graph(GraphPayload.model_validate(json.loads(FIXTURE.read_text())))
    yield


def test_filtered_subgraph_isolates_time_window() -> None:
    sub = engine.get_filtered_subgraph("2026-01-14T00:00:00", "2026-01-15T23:59:59")
    types = {d["type"] for _, _, d in sub.edges(data=True)}
    assert types == {"TRANSFERRED"}
    assert sub.number_of_edges() == 3
    # Main graph untouched.
    assert engine.get_graph().number_of_edges() == 23


def test_open_ended_and_timeless_edges() -> None:
    only_start = engine.get_filtered_subgraph(start_time="2026-01-14T00:00:00")
    assert only_start.number_of_edges() == 3
    only_end = engine.get_filtered_subgraph(end_time="2026-01-06T23:59:59")
    assert only_end.number_of_edges() == 3  # three USES edges, timeless CO_ACCUSED excluded
    full_copy = engine.get_filtered_subgraph()
    assert full_copy.number_of_edges() == 23


def test_time_range_matches_fixture() -> None:
    assert engine.get_time_range() == {
        "earliest": "2026-01-05T09:00:00",
        "latest": "2026-01-15T14:05:00",
    }


def test_cytoscape_schema_shape() -> None:
    body = engine.get_cytoscape_elements()
    assert set(body) == {"elements"}
    node = body["elements"]["nodes"][0]["data"]
    assert {"id", "label", "type", "betweenness", "pagerank", "community_id", "metadata"} <= set(node)
    edge = body["elements"]["edges"][0]["data"]
    assert {"id", "source", "target", "type", "timestamp", "amount", "metadata"} <= set(edge)


def test_api_graph_returns_cytoscape_structure() -> None:
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    elements = resp.json()["elements"]
    assert len(elements["nodes"]) == 11
    assert len(elements["edges"]) == 23


def test_api_graph_time_window_filters() -> None:
    resp = client.get(
        "/api/graph",
        params={"start_time": "2026-01-14T00:00:00", "end_time": "2026-01-15T23:59:59"},
    )
    assert resp.status_code == 200
    elements = resp.json()["elements"]
    assert len(elements["edges"]) == 3
    assert {e["data"]["type"] for e in elements["edges"]} == {"TRANSFERRED"}
    node_ids = {n["data"]["id"] for n in elements["nodes"]}
    assert node_ids == {"acct_mule1", "acct_mule2", "acct_arif"}


def test_api_time_range_and_bad_input() -> None:
    assert client.get("/api/graph/time-range").json() == {
        "earliest": "2026-01-05T09:00:00",
        "latest": "2026-01-15T14:05:00",
    }
    bad = client.get("/api/graph", params={"start_time": "not-a-date"})
    assert bad.status_code == 400
