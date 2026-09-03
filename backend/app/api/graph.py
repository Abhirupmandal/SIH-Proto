"""Graph read routes. Thin HTTP layer over GraphEngine."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.graph_store import engine, get_engine

router = APIRouter(prefix="/api", tags=["graph"])

__all__ = ["router", "engine", "get_engine"]


@router.get("/graph")
def read_graph(
    start_time: str | None = None, end_time: str | None = None
) -> dict[str, Any]:
    """Return Cytoscape.js elements, optionally time-windowed."""
    try:
        if start_time is None and end_time is None:
            return engine.get_cytoscape_elements()
        subgraph = engine.get_filtered_subgraph(start_time, end_time)
        return engine.get_cytoscape_elements(subgraph)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/graph/time-range")
def read_time_range() -> dict[str, str | None]:
    """Return earliest/latest edge timestamps in the graph."""
    return engine.get_time_range()
