"""Stage 2 Data Contract: strict validation for Member 1 graph payload.

Independent from FastAPI routes and NetworkX logic.
Uses Pydantic v2 syntax only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NodeType = Literal["Suspect", "Phone", "Account", "Location", "CrimeCase"]
EdgeType = Literal["CALLED", "TRANSFERRED", "OPERATES", "USES", "CO_ACCUSED_IN"]


class EdgeMetadataModel(BaseModel):
    """Optional standard + evidence metadata for an edge."""

    model_config = ConfigDict(extra="allow")

    timestamp: str | datetime | None = None
    amount: float | int | None = None
    duration: float | int | None = None

    transaction_id: str | None = None
    cdr_id: str | None = None
    fir_id: str | None = None
    fir_excerpt: str | None = None
    source_document: str | None = None


class EdgeModel(BaseModel):
    """A directed relationship between two nodes."""

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: EdgeType
    metadata: EdgeMetadataModel = Field(default_factory=EdgeMetadataModel)


class NodeMetadataModel(BaseModel):
    """Free-form node metadata. Unknown fields are allowed."""

    model_config = ConfigDict(extra="allow")


class NodeModel(BaseModel):
    """A single entity in the criminal network."""

    id: str = Field(min_length=1)
    type: NodeType
    label: str = Field(min_length=1)
    metadata: NodeMetadataModel = Field(default_factory=NodeMetadataModel)


class GraphPayload(BaseModel):
    """Top-level payload produced by Member 1."""

    nodes: list[NodeModel]
    edges: list[EdgeModel]
