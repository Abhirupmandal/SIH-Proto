"""Tests for Stage 3 GraphEngine core (storage, ingestion, stats)."""

import networkx as nx

from app.core.graph_engine import GraphEngine
from app.models.graph_models import EdgeModel, GraphPayload, NodeModel


def _sample_payload() -> GraphPayload:
    return GraphPayload.model_validate(
        {
            "nodes": [
                {"id": "suspect_1", "type": "Suspect", "label": "Accused A"},
                {
                    "id": "phone_1",
                    "type": "Phone",
                    "label": "+91-98XXXXXX01",
                    "metadata": {"carrier": "Jio"},
                },
                {"id": "acc_1", "type": "Account", "label": "XXXX-1234"},
            ],
            "edges": [
                {
                    "source": "suspect_1",
                    "target": "phone_1",
                    "type": "USES",
                },
                {
                    "source": "phone_1",
                    "target": "phone_1",
                    "type": "CALLED",
                    "metadata": {
                        "duration": 320,
                        "cdr_id": "CDR-991",
                        "fir_id": "FIR-42-2026",
                    },
                },
            ],
        }
    )


def test_add_node_preserves_metadata() -> None:
    engine = GraphEngine()
    engine.add_node(
        NodeModel.model_validate(
            {
                "id": "suspect_1",
                "type": "Suspect",
                "label": "Accused A",
                "metadata": {"age": 34, "custom_flag": "x"},
            }
        )
    )
    data = engine.get_graph().nodes["suspect_1"]
    assert data["type"] == "Suspect"
    assert data["label"] == "Accused A"
    assert data["age"] == 34
    assert data["custom_flag"] == "x"


def test_parallel_edges_between_same_pair_preserved() -> None:
    engine = GraphEngine()
    engine.add_node(NodeModel.model_validate({"id": "a", "type": "Phone", "label": "A"}))
    engine.add_node(NodeModel.model_validate({"id": "b", "type": "Phone", "label": "B"}))

    id1 = engine.add_edge(
        EdgeModel.model_validate(
            {"source": "a", "target": "b", "type": "CALLED", "metadata": {"duration": 60}}
        )
    )
    id2 = engine.add_edge(
        EdgeModel.model_validate(
            {"source": "a", "target": "b", "type": "CALLED", "metadata": {"duration": 120}}
        )
    )
    assert id1 != id2
    assert engine.get_graph().number_of_edges() == 2
    # Both parallel edges retrievable by their unique keys.
    assert engine.get_graph()[ "a"]["b"][id1]["duration"] == 60
    assert engine.get_graph()["a"]["b"][id2]["duration"] == 120


def test_edge_metadata_not_discarded() -> None:
    engine = GraphEngine()
    engine.add_edge(
        EdgeModel.model_validate(
            {
                "source": "x",
                "target": "y",
                "type": "TRANSFERRED",
                "metadata": {
                    "amount": 50000,
                    "timestamp": "2026-01-15T10:30:00",
                    "transaction_id": "TXN-001",
                    "fir_id": "FIR-1",
                },
            }
        )
    )
    _, _, data = next(iter(engine.get_graph().edges(data=True)))
    assert data["amount"] == 50000
    assert data["transaction_id"] == "TXN-001"
    assert data["fir_id"] == "FIR-1"
    assert data["timestamp"] == "2026-01-15T10:30:00"
    assert data["type"] == "TRANSFERRED"
    assert "edge_id" in data


def test_dangling_edge_endpoints_handled_cleanly() -> None:
    engine = GraphEngine()
    engine.add_edge(
        EdgeModel.model_validate({"source": "ghost_1", "target": "ghost_2", "type": "USES"})
    )
    # Auto-created placeholders instead of crashing.
    assert "ghost_1" in engine.get_graph()
    assert "ghost_2" in engine.get_graph()
    assert engine.get_graph().number_of_edges() == 1


def test_load_graph_populates_and_clears() -> None:
    engine = GraphEngine()
    engine.add_node(NodeModel.model_validate({"id": "stale", "type": "Phone", "label": "S"}))

    engine.load_graph(_sample_payload())
    graph = engine.get_graph()
    assert isinstance(graph, nx.MultiDiGraph)
    assert "stale" not in graph  # cleared
    assert graph.number_of_nodes() == 3
    assert graph.number_of_edges() == 2
    assert graph.nodes["phone_1"]["carrier"] == "Jio"


def test_get_stats_counts_by_type() -> None:
    engine = GraphEngine()
    engine.load_graph(_sample_payload())
    assert engine.get_stats() == {
        "total_nodes": 3,
        "total_edges": 2,
        "node_types": {"Suspect": 1, "Phone": 1, "Account": 1},
        "edge_types": {"USES": 1, "CALLED": 1},
    }


def test_clear_graph_resets() -> None:
    engine = GraphEngine()
    engine.load_graph(_sample_payload())
    engine.clear_graph()
    assert engine.get_graph().number_of_nodes() == 0
    assert engine.get_stats()["total_edges"] == 0
