"""Graph storage, ingestion, manipulation, core analytics, and temporal views.

Deliberately free of FastAPI imports so graph logic stays
reusable and testable.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime
from typing import Any

import community as community_louvain
import networkx as nx

from app.models.graph_models import EdgeModel, GraphPayload, NodeModel


class GraphEngine:
    """In-memory criminal network backed by a directed multigraph."""

    def __init__(self) -> None:
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()

    def clear_graph(self) -> None:
        """Reset the internal graph to empty."""
        self.graph.clear()

    def get_graph(self) -> nx.MultiDiGraph:
        """Return the internal graph object."""
        return self.graph

    def add_node(self, node: NodeModel) -> None:
        """Add a node with type, label, and unpacked metadata."""
        attrs: dict = {
            "type": node.type,
            "label": node.label,
            **node.metadata.model_dump(),
        }
        self.graph.add_node(node.id, **attrs)

    def add_edge(self, edge: EdgeModel) -> str:
        """Add a directed edge, preserving parallel edges.

        Missing endpoint nodes are auto-created as lightweight
        placeholders so dangling references never crash ingestion.
        Returns the generated edge_id (also used as MultiDiGraph key).
        """
        for node_id in (edge.source, edge.target):
            if node_id not in self.graph:
                self.graph.add_node(node_id, type="Unknown", label=node_id)

        edge_id = f"edge_{uuid.uuid4().hex}"
        attrs: dict = {
            "type": edge.type,
            "edge_id": edge_id,
            **edge.metadata.model_dump(exclude_none=True),
        }
        # Extra (unknown) metadata fields live in model_extra when
        # exclude_none drops nothing extra, but model_dump already
        # includes them; merge explicitly for clarity/safety.
        if edge.metadata.model_extra:
            attrs.update(edge.metadata.model_extra)

        self.graph.add_edge(edge.source, edge.target, key=edge_id, **attrs)
        return edge_id

    def load_graph(self, payload: GraphPayload) -> None:
        """Clear existing graph and load all nodes/edges from payload."""
        self.clear_graph()
        for node in payload.nodes:
            self.add_node(node)
        for edge in payload.edges:
            self.add_edge(edge)

    def get_stats(self) -> dict:
        """Return count summary of nodes and edges by type."""
        node_types = Counter(
            data.get("type", "Unknown") for _, data in self.graph.nodes(data=True)
        )
        edge_types = Counter(
            data.get("type", "Unknown") for _, _, data in self.graph.edges(data=True)
        )
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": dict(node_types),
            "edge_types": dict(edge_types),
        }

    # ---- Core analytics (Stage 5) ----

    def _to_weighted_undirected(self) -> nx.Graph:
        """Collapse MultiDiGraph into a weighted simple undirected graph.

        Edge weight between a pair equals the total number of
        interactions/transfers (parallel directed edges counted).
        Isolated nodes are preserved.
        """
        undirected = nx.Graph()
        undirected.add_nodes_from(self.graph.nodes())
        for u, v in self.graph.edges():
            if undirected.has_edge(u, v):
                undirected[u][v]["weight"] += 1
            else:
                undirected.add_edge(u, v, weight=1)
        return undirected

    def compute_metrics(self) -> dict[str, dict[str, Any]]:
        """Compute betweenness, PageRank, Louvain communities.

        Attaches ``betweenness``, ``pagerank``, ``community_id`` as node
        attributes. Safe on empty, single-node, or isolated-node graphs.
        """
        if self.graph.number_of_nodes() == 0:
            return {"betweenness": {}, "pagerank": {}, "community": {}}

        try:
            betweenness = nx.betweenness_centrality(self.graph)
        except Exception:
            betweenness = {n: 0.0 for n in self.graph.nodes()}

        try:
            pagerank = nx.pagerank(self.graph)
        except Exception:
            n = self.graph.number_of_nodes()
            pagerank = {node: 1.0 / n for node in self.graph.nodes()}

        try:
            partition = community_louvain.best_partition(
                self._to_weighted_undirected(), weight="weight", random_state=42
            )
        except Exception:
            partition = {n: 0 for n in self.graph.nodes()}

        for node in self.graph.nodes():
            self.graph.nodes[node]["betweenness"] = float(betweenness.get(node, 0.0))
            self.graph.nodes[node]["pagerank"] = float(pagerank.get(node, 0.0))
            self.graph.nodes[node]["community_id"] = int(partition.get(node, 0))

        return {
            "betweenness": {n: float(v) for n, v in betweenness.items()},
            "pagerank": {n: float(v) for n, v in pagerank.items()},
            "community": {n: int(v) for n, v in partition.items()},
        }

    def _node_summary(self, node_id: str) -> dict[str, Any]:
        data = self.graph.nodes[node_id]
        return {
            "node_id": node_id,
            "label": data.get("label", node_id),
            "type": data.get("type", "Unknown"),
            "betweenness": float(data.get("betweenness", 0.0)),
            "pagerank": float(data.get("pagerank", 0.0)),
            "community_id": int(data.get("community_id", 0)),
        }

    def get_top_betweenness(self, limit: int = 5) -> list[dict[str, Any]]:
        """Top nodes sorted descending by betweenness."""
        ranked = sorted(
            self.graph.nodes(),
            key=lambda n: float(self.graph.nodes[n].get("betweenness", 0.0)),
            reverse=True,
        )
        return [self._node_summary(n) for n in ranked[:limit]]

    def get_top_pagerank(self, limit: int = 5) -> list[dict[str, Any]]:
        """Top nodes sorted descending by PageRank."""
        ranked = sorted(
            self.graph.nodes(),
            key=lambda n: float(self.graph.nodes[n].get("pagerank", 0.0)),
            reverse=True,
        )
        return [self._node_summary(n) for n in ranked[:limit]]

    def get_communities(self) -> dict[int, list[str]]:
        """Group node ids by their community_id."""
        grouped: dict[int, list[str]] = {}
        for node in self.graph.nodes():
            cid = int(self.graph.nodes[node].get("community_id", 0))
            grouped.setdefault(cid, []).append(node)
        return grouped

    # ---- Temporal filtering + Cytoscape export (Stages 6 & 7) ----

    @staticmethod
    def _parse_time(value: str | datetime | None, *, label: str) -> datetime | None:
        """Parse an ISO-8601 bound or edge timestamp.

        Returns None for missing values. Raises ValueError for
        non-empty unparseable strings.
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError(f"Invalid {label}: {value!r}. Use ISO-8601.") from None
        return None

    @staticmethod
    def _as_naive(dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt

    def get_filtered_subgraph(
        self, start_time: str | None = None, end_time: str | None = None
    ) -> nx.MultiDiGraph:
        """Return a NEW graph with only edges in [start_time, end_time].

        Bounds are ISO-8601 strings; missing bounds are unbounded.
        Edges with missing/unparseable timestamps are excluded when a
        window is given, included when no window is given. The main
        graph is never mutated; only nodes touching kept edges are
        included in windowed views.
        """
        start = self._parse_time(start_time, label="start_time")
        end = self._parse_time(end_time, label="end_time")
        if start is not None:
            start = self._as_naive(start)
        if end is not None:
            end = self._as_naive(end)

        if start is None and end is None:
            return self.graph.copy()

        filtered = nx.MultiDiGraph()
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            try:
                ts = self._parse_time(data.get("timestamp"), label="edge timestamp")
            except ValueError:
                continue
            if ts is None:
                continue
            ts = self._as_naive(ts)
            if start is not None and ts < start:
                continue
            if end is not None and ts > end:
                continue
            for node_id in (u, v):
                if node_id not in filtered and node_id in self.graph.nodes:
                    filtered.add_node(node_id, **dict(self.graph.nodes[node_id]))
            filtered.add_edge(u, v, key=key, **dict(data))
        return filtered

    def get_time_range(self) -> dict[str, str | None]:
        """Scan edge timestamps, return earliest/latest ISO strings."""
        stamps: list[datetime] = []
        for _, _, data in self.graph.edges(data=True):
            try:
                ts = self._parse_time(data.get("timestamp"), label="edge timestamp")
            except ValueError:
                continue
            if ts is not None:
                stamps.append(self._as_naive(ts))
        if not stamps:
            return {"earliest": None, "latest": None}
        return {
            "earliest": min(stamps).isoformat(),
            "latest": max(stamps).isoformat(),
        }

    @staticmethod
    def _json_safe(value: Any) -> Any:
        return value.isoformat() if isinstance(value, datetime) else value

    def get_cytoscape_elements(
        self, subgraph: nx.MultiDiGraph | None = None
    ) -> dict[str, dict[str, list[dict[str, dict[str, Any]]]]]:
        """Return Cytoscape.js-ready ``{elements: {nodes, edges}}``.

        Uses ``subgraph`` when given, else the full graph. Runs
        ``compute_metrics()`` first if the main graph lacks centrality
        attributes; windowed copies backfill metrics from the main graph.
        """
        target = self.graph if subgraph is None else subgraph

        if any(
            "betweenness" not in self.graph.nodes[n] for n in self.graph.nodes()
        ):
            self.compute_metrics()

        nodes: list[dict[str, dict[str, Any]]] = []
        for node_id, data in target.nodes(data=True):
            main = self.graph.nodes[node_id] if node_id in self.graph.nodes else {}
            metadata = {
                k: self._json_safe(v)
                for k, v in data.items()
                if k not in {"type", "label", "betweenness", "pagerank", "community_id"}
            }
            nodes.append(
                {
                    "data": {
                        "id": node_id,
                        "label": data.get("label", node_id),
                        "type": data.get("type", "Unknown"),
                        "betweenness": float(
                            data.get("betweenness", main.get("betweenness", 0.0))
                        ),
                        "pagerank": float(
                            data.get("pagerank", main.get("pagerank", 0.0))
                        ),
                        "community_id": int(
                            data.get("community_id", main.get("community_id", 0))
                        ),
                        "metadata": metadata,
                    }
                }
            )

        edges: list[dict[str, dict[str, Any]]] = []
        for u, v, key, data in target.edges(keys=True, data=True):
            metadata = {
                k: self._json_safe(val)
                for k, val in data.items()
                if k not in {"type", "edge_id", "timestamp", "amount"}
            }
            edges.append(
                {
                    "data": {
                        "id": data.get("edge_id", key),
                        "source": u,
                        "target": v,
                        "type": data.get("type", "Unknown"),
                        "timestamp": self._json_safe(data.get("timestamp")),
                        "amount": data.get("amount"),
                        "metadata": metadata,
                    }
                }
            )
        return {"elements": {"nodes": nodes, "edges": edges}}
