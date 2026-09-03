"""Shared GraphEngine singleton + fixture bootstrap.

Single source of truth for all API routers so ingest, analytics,
evidence, dossier, and graph views always see the same data.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.graph_engine import GraphEngine
from app.models.graph_models import GraphPayload

engine = GraphEngine()


def ensure_sample_loaded() -> bool:
    """Load Stage 4 fixture if the engine is empty. Returns True if loaded."""
    if engine.get_graph().number_of_nodes():
        return False
    candidate = (
        Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "sample_graph.json"
    )
    if not candidate.exists():
        return False
    payload = GraphPayload.model_validate(json.loads(candidate.read_text()))
    engine.load_graph(payload)
    return True


def get_engine() -> GraphEngine:
    """Return the shared engine."""
    return engine


ensure_sample_loaded()
