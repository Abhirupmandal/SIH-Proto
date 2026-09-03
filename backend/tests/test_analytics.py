"""Tests for Stage 5 core graph analytics (centrality, PageRank, Louvain)."""

import json
from pathlib import Path

import pytest

from app.core.graph_engine import GraphEngine
from app.models.graph_models import GraphPayload, NodeModel

FIXTURE = Path(__file__).parent / "fixtures" / "sample_graph.json"


def _loaded_engine() -> GraphEngine:
    payload = GraphPayload.model_validate(json.loads(FIXTURE.read_text()))
    engine = GraphEngine()
    engine.load_graph(payload)
    return engine


def test_fixture_loads_expected_shape() -> None:
    engine = _loaded_engine()
    stats = engine.get_stats()
    assert stats["total_nodes"] == 11
    assert stats["total_edges"] == 23
    assert stats["node_types"]["Suspect"] == 4
    assert set(stats["edge_types"]) >= {"CALLED", "TRANSFERRED", "USES", "OPERATES", "CO_ACCUSED_IN"}


def test_compute_metrics_attaches_numeric_attributes() -> None:
    engine = _loaded_engine()
    engine.compute_metrics()
    assert engine.get_graph().number_of_nodes() == 11
    for node, data in engine.get_graph().nodes(data=True):
        assert isinstance(data["betweenness"], float), node
        assert isinstance(data["pagerank"], float), node
        assert isinstance(data["community_id"], int), node
        assert 0.0 <= data["betweenness"] <= 1.0
        assert data["pagerank"] >= 0.0


def test_kingpin_and_cell_structure() -> None:
    engine = _loaded_engine()
    engine.compute_metrics()
    top = engine.get_top_betweenness(limit=5)
    # Arif bridges Ramesh to the Bunty/Vicky cell -> highest betweenness.
    assert top[0]["node_id"] == "suspect_arif"
    communities = engine.get_communities()
    inv = {n: cid for cid, members in communities.items() for n in members}
    # Tightly coupled Bunty/Vicky cell shares a community.
    assert inv["suspect_bunty"] == inv["suspect_vicky"]


def test_top_betweenness_sorted_and_shaped() -> None:
    engine = _loaded_engine()
    engine.compute_metrics()
    top = engine.get_top_betweenness(limit=5)
    assert len(top) == 5
    scores = [t["betweenness"] for t in top]
    assert scores == sorted(scores, reverse=True)
    for entry in top:
        assert set(entry) == {"node_id", "label", "type", "betweenness", "pagerank", "community_id"}


def test_top_pagerank_sorted() -> None:
    engine = _loaded_engine()
    engine.compute_metrics()
    top = engine.get_top_pagerank(limit=5)
    scores = [t["pagerank"] for t in top]
    assert scores == sorted(scores, reverse=True)


def test_get_communities_covers_all_nodes() -> None:
    engine = _loaded_engine()
    engine.compute_metrics()
    grouped = engine.get_communities()
    total = sum(len(members) for members in grouped.values())
    assert total == 11


def test_empty_graph_does_not_crash() -> None:
    engine = GraphEngine()
    assert engine.compute_metrics() == {"betweenness": {}, "pagerank": {}, "community": {}}
    assert engine.get_top_betweenness() == []
    assert engine.get_top_pagerank() == []
    assert engine.get_communities() == {}


@pytest.mark.parametrize("n", [1, 2])
def test_degenerate_graphs_do_not_crash(n: int) -> None:
    engine = GraphEngine()
    for i in range(n):
        engine.add_node(
            NodeModel.model_validate({"id": f"lone_{i}", "type": "Phone", "label": f"P{i}"})
        )
    engine.compute_metrics()
    for _, data in engine.get_graph().nodes(data=True):
        assert isinstance(data["betweenness"], float)
        assert isinstance(data["pagerank"], float)
        assert isinstance(data["community_id"], int)
