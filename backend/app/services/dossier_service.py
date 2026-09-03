"""In-memory PDF dossier builder (ReportLab) over GraphEngine state."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.graph_engine import GraphEngine


def _evidence_score(data: dict[str, Any]) -> int:
    return sum(
        1
        for key in ("fir_excerpt", "cdr_id", "transaction_id", "fir_id")
        if data.get(key)
    )


def build_dossier_pdf(engine: GraphEngine, top_n: int = 10) -> bytes:
    """Assemble the investigative dossier PDF and return raw bytes."""
    graph = engine.get_graph()
    if any("betweenness" not in graph.nodes[n] for n in graph.nodes()):
        engine.compute_metrics()

    stats = engine.get_stats()
    communities = engine.get_communities()
    leaders = engine.get_top_betweenness(limit=top_n)

    key_edges = sorted(
        (
            (u, v, key, data)
            for u, v, key, data in graph.edges(keys=True, data=True)
        ),
        key=lambda item: (_evidence_score(item[3]), str(item[3].get("timestamp") or "")),
        reverse=True,
    )[:top_n]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Investigative Dossier")
    styles = getSampleStyleSheet()
    story: list[Any] = [
        Paragraph("CRIMINAL NETWORK INVESTIGATIVE DOSSIER", styles["Title"]),
        Paragraph(
            f"Generated: {datetime.now(timezone.utc).isoformat()} | "
            "Analytical assessment — leads only, not conclusions of guilt.",
            styles["Normal"],
        ),
        Spacer(1, 12),
        Paragraph("1. Summary Metrics", styles["Heading2"]),
        Paragraph(
            f"Total Nodes: {stats['total_nodes']} | "
            f"Total Edges: {stats['total_edges']} | "
            f"Number of Communities: {len(communities)}",
            styles["Normal"],
        ),
        Spacer(1, 12),
        Paragraph("2. High-Centrality Nodes", styles["Heading2"]),
        Paragraph(
            "Ranked broker candidates: high-centrality candidates whose position "
            "on shortest paths suggests a possible coordination role. "
            "Treat as investigative leads.",
            styles["Normal"],
        ),
        Spacer(1, 6),
    ]

    table_data = [["Rank", "Label", "Type", "Betweenness", "PageRank", "Community"]]
    for i, entry in enumerate(leaders, start=1):
        table_data.append(
            [
                str(i),
                str(entry["label"]),
                str(entry["type"]),
                f"{entry['betweenness']:.4f}",
                f"{entry['pagerank']:.4f}",
                str(entry["community_id"]),
            ]
        )
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story += [table, Spacer(1, 12)]

    story += [
        Paragraph("3. Key Evidence Trail", styles["Heading2"]),
        Paragraph(
            "Each observed relationship below links the recorded endpoints to "
            "its supporting evidence (FIR excerpts, CDR IDs, transaction IDs).",
            styles["Normal"],
        ),
        Spacer(1, 6),
    ]
    if not key_edges:
        story.append(Paragraph("No observed relationships with evidence recorded.", styles["Normal"]))
    for u, v, _key, data in key_edges:
        story.append(
            Paragraph(
                f"Observed relationship {data.get('type', 'Unknown')}: {u} -&gt; {v} | "
                f"CDR: {data.get('cdr_id') or '-'} | "
                f"Transaction: {data.get('transaction_id') or '-'} | "
                f"FIR: {data.get('fir_id') or '-'}",
                styles["Normal"],
            )
        )
        if data.get("fir_excerpt"):
            story.append(Paragraph(f"Excerpt: {data['fir_excerpt']}", styles["Normal"]))
        story.append(Spacer(1, 6))

    doc.build(story)
    return buf.getvalue()
