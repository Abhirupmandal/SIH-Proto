"""Strict validation tests for the Stage 2 graph data contract."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.graph_models import (
    EdgeMetadataModel,
    EdgeModel,
    GraphPayload,
    NodeMetadataModel,
    NodeModel,
)


def _valid_payload() -> dict:
    return {
        "nodes": [
            {"id": "suspect_1", "type": "Suspect", "label": "Accused A"},
            {"id": "phone_1", "type": "Phone", "label": "+91-98XXXXXX01"},
            {"id": "case_1", "type": "CrimeCase", "label": "FIR 42/2026"},
        ],
        "edges": [
            {
                "source": "suspect_1",
                "target": "phone_1",
                "type": "USES",
            },
            {
                "source": "suspect_1",
                "target": "case_1",
                "type": "CO_ACCUSED_IN",
                "metadata": {
                    "fir_id": "FIR-42-2026",
                    "fir_excerpt": "Named as co-accused in FIR excerpt...",
                    "source_document": "fir_42_2026.pdf",
                },
            },
        ],
    }


def test_valid_payload_passes_validation() -> None:
    payload = GraphPayload.model_validate(_valid_payload())
    assert len(payload.nodes) == 3
    assert len(payload.edges) == 2
    # Omitted metadata defaults to empty models.
    assert isinstance(payload.edges[0].metadata, EdgeMetadataModel)
    assert isinstance(payload.nodes[0].metadata, NodeMetadataModel)


def test_missing_edge_source_raises() -> None:
    with pytest.raises(ValidationError):
        EdgeModel.model_validate({"target": "phone_1", "type": "USES"})


def test_missing_node_id_raises() -> None:
    with pytest.raises(ValidationError):
        NodeModel.model_validate({"type": "Suspect", "label": "No id"})


def test_empty_string_id_and_source_rejected() -> None:
    with pytest.raises(ValidationError):
        NodeModel.model_validate({"id": "", "type": "Suspect", "label": "x"})
    with pytest.raises(ValidationError):
        EdgeModel.model_validate({"source": "", "target": "b", "type": "CALLED"})


def test_custom_metadata_fields_pass_without_errors() -> None:
    node = NodeModel.model_validate(
        {
            "id": "acc_1",
            "type": "Account",
            "label": "XXXX-1234",
            "metadata": {"bank": "SBI", "custom_score": 0.87, "nested": {"a": 1}},
        }
    )
    assert node.metadata.model_extra["bank"] == "SBI"
    assert node.metadata.model_extra["custom_score"] == 0.87

    edge = EdgeModel.model_validate(
        {
            "source": "a",
            "target": "b",
            "type": "TRANSFERRED",
            "metadata": {"amount": 50000, "some_future_field": "kept"},
        }
    )
    assert edge.metadata.amount == 50000
    assert edge.metadata.model_extra["some_future_field"] == "kept"


def test_optional_evidence_fields_populate_correctly() -> None:
    edge = EdgeModel.model_validate(
        {
            "source": "phone_1",
            "target": "phone_2",
            "type": "CALLED",
            "metadata": {
                "timestamp": "2026-01-15T10:30:00",
                "duration": 320,
                "cdr_id": "CDR-991",
                "transaction_id": "TXN-001",
                "fir_id": "FIR-42-2026",
                "fir_excerpt": "Call noted in CDR excerpt",
                "source_document": "cdr_jan2026.csv",
            },
        }
    )
    assert edge.metadata.cdr_id == "CDR-991"
    assert edge.metadata.transaction_id == "TXN-001"
    assert edge.metadata.fir_id == "FIR-42-2026"
    assert edge.metadata.fir_excerpt == "Call noted in CDR excerpt"
    assert edge.metadata.source_document == "cdr_jan2026.csv"
    assert edge.metadata.duration == 320


def test_datetime_timestamp_accepted() -> None:
    edge = EdgeModel.model_validate(
        {
            "source": "a",
            "target": "b",
            "type": "CALLED",
            "metadata": {"timestamp": datetime(2026, 1, 15, 10, 30)},
        }
    )
    assert isinstance(edge.metadata.timestamp, datetime)


def test_invalid_edge_type_rejected() -> None:
    with pytest.raises(ValidationError):
        EdgeModel.model_validate({"source": "a", "target": "b", "type": "FRIENDS_WITH"})
