"""High-risk node ranking routes. Thin layer over GraphEngine."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.services.graph_store import engine

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/high-risk")
def high_risk(limit: int = Query(default=5, ge=1, le=50)) -> dict[str, Any]:
    """Rank nodes by betweenness centrality (broker candidates)."""
    if any("betweenness" not in engine.get_graph().nodes[n] for n in engine.get_graph().nodes()):
        engine.compute_metrics()
    top = engine.get_top_betweenness(limit)
    return {
        "results": [
            {
                "rank": i,
                "node_id": entry["node_id"],
                "label": entry["label"],
                "type": entry["type"],
                "betweenness": entry["betweenness"],
                "pagerank": entry["pagerank"],
                "community_id": entry["community_id"],
            }
            for i, entry in enumerate(top, start=1)
        ]
    }
