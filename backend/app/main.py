"""FastAPI application entrypoint.

Keeps HTTP concerns here only. All graph logic lives in
app.core.graph_engine and services.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.dossier import router as dossier_router
from app.api.evidence import router as evidence_router
from app.api.graph import router as graph_router
from app.api.health import router as health_router
from app.models.graph_models import GraphPayload
from app.services.graph_store import engine, ensure_sample_loaded


def create_app() -> FastAPI:
    app = FastAPI(title="Graph Intelligence API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    ensure_sample_loaded()
    app.include_router(health_router)
    app.include_router(graph_router)
    app.include_router(analytics_router)
    app.include_router(evidence_router)
    app.include_router(dossier_router)

    @app.post("/api/ingest")
    def ingest(payload: GraphPayload) -> dict[str, Any]:
        """Dynamically reload the shared GraphEngine from a payload."""
        engine.load_graph(payload)
        return {"status": "loaded", "stats": engine.get_stats()}

    return app


app = create_app()
