"""Dossier export route. Thin layer over the dossier service."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from app.services.dossier_service import build_dossier_pdf
from app.services.graph_store import engine

router = APIRouter(prefix="/api", tags=["dossier"])


@router.get("/export-dossier")
def export_dossier() -> Response:
    """Return the investigative dossier as a PDF download."""
    pdf = build_dossier_pdf(engine)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="investigative_dossier.pdf"'},
    )
