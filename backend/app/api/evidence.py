"""Evidence-trail routes. Thin layer over the evidence service."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.evidence_service import EvidenceNotFoundError, get_evidence_trail
from app.services.graph_store import engine

router = APIRouter(prefix="/api", tags=["evidence"])


@router.get("/evidence-trail")
def evidence_trail(
    source: str, target: str, bidirectional: bool = False
) -> dict[str, Any]:
    """Return every observed relationship between two nodes."""
    try:
        return get_evidence_trail(engine, source, target, bidirectional)
    except EvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
