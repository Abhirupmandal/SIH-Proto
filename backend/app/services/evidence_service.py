"""Evidence-trail (XAI) lookup over GraphEngine parallel edges."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.graph_engine import GraphEngine


class EvidenceNotFoundError(LookupError):
    """Raised when nodes are missing or no relationships exist."""


def _json_safe(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def get_evidence_trail(
    engine: GraphEngine,
    source: str,
    target: str,
    bidirectional: bool = False,
) -> dict[str, Any]:
    """Collect ALL edges between source and target with full metadata.

    Raises EvidenceNotFoundError if either node is missing or no
    relationships are found.
    """
    graph = engine.get_graph()
    if source not in graph or target not in graph:
        raise EvidenceNotFoundError(f"Unknown node: {source!r} or {target!r}.")

    pairs = [(source, target)]
    if bidirectional and target != source:
        pairs.append((target, source))

    relationships: list[dict[str, Any]] = []
    for u, v in pairs:
        edge_data = graph.get_edge_data(u, v, default={})
        for key, data in edge_data.items():
            relationships.append(
                {
                    "edge_id": data.get("edge_id", key),
                    "type": data.get("type", "Unknown"),
                    "timestamp": _json_safe(data.get("timestamp")),
                    "amount": data.get("amount"),
                    "duration": data.get("duration"),
                    "transaction_id": data.get("transaction_id"),
                    "cdr_id": data.get("cdr_id"),
                    "fir_id": data.get("fir_id"),
                    "fir_excerpt": data.get("fir_excerpt"),
                    "source_document": data.get("source_document"),
                }
            )

    if not relationships:
        raise EvidenceNotFoundError(f"No relationships between {source!r} and {target!r}.")

    return {
        "source": {"id": source, "label": graph.nodes[source].get("label", source)},
        "target": {"id": target, "label": graph.nodes[target].get("label", target)},
        "relationships": relationships,
    }
