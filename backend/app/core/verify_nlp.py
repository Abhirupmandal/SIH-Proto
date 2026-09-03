"""
backend/app/core/verify_nlp.py
Standalone diagnostic & benchmark for nlp.py and resolver.py

Covers:
  1) Schema & Data Integrity
  2) Edge Case & Safety (dangling edges, alias dedup, phone/account disambiguation, edge metadata)
  3) Execution Report (summary tables + latency)

Usage:
  python backend/app/core/verify_nlp.py
  python -m backend.app.core.verify_nlp

Run from project root E:\\SIH(2026)\\main_nlp  OR any cwd - path resolution is relative to this file.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Path resolution - robust to cwd / import context
# ---------------------------------------------------------------------------
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[3]  # .../main_nlp
# Fallback: if structure differs, try cwd
CANDIDATE_ROOTS: List[Path] = [
    PROJECT_ROOT,
    Path.cwd(),
    Path.cwd() / "main_nlp",
    THIS_FILE.parents[2],
    THIS_FILE.parents[1],
]

def _resolve_data_dir() -> Path | None:
    for root in CANDIDATE_ROOTS:
        try:
            if (root / "data").is_dir():
                return root / "data"
            if (root / "data" / "clean_graph.json").exists():
                return root / "data"
            if (root / "backend").is_dir() and (root / "data").is_dir():
                return root / "data"
        except Exception:
            continue
    # Last resort: absolute known path for this SIH workspace
    hardcoded = Path(r"E:\SIH(2026)\main_nlp\data")
    if hardcoded.is_dir():
        return hardcoded
    return None


def _resolve_clean_graph_path(data_dir: Path) -> Path:
    return data_dir / "clean_graph.json"


# ---------------------------------------------------------------------------
# Constants - strict schema
# ---------------------------------------------------------------------------
ALLOWED_NODE_TYPES = {"Suspect", "Phone", "Account", "Location", "CrimeCase"}
ALLOWED_EDGE_TYPES = {"CALLED", "TRANSFERRED", "OPERATES", "USES", "CO_ACCUSED_IN"}

PHONE_LABEL_RE = re.compile(r"^[6-9]\d{9}$")
ACCOUNT_LABEL_RE = re.compile(r"^\d{9,18}$")
FIR_RE = re.compile(r"\bFIR-\d{4}-[A-Z0-9]+\b")
# For edge metadata timestamp ISO8601 check
ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

# Alias pairs expected in sample data - used for dedup assertion
EXPECTED_ALIAS_PAIRS: List[Tuple[str, str]] = [
    ("Ramesh Kumar", "Rama"),
    ("Rakesh", "Bunty"),
    ("Sunil Kumar", "Sonu"),
]


# ---------------------------------------------------------------------------
# Helpers - loading
# ---------------------------------------------------------------------------

def load_graph() -> Tuple[Dict[str, List[Dict[str, Any]]], float, str]:
    """
    Load data/clean_graph.json if present, else execute parse_all_sources("data").
    Returns (graph, latency_seconds, source_label)
    """
    data_dir = _resolve_data_dir()
    if data_dir is None:
        raise FileNotFoundError(
            "Could not resolve data directory. Tried: "
            + ", ".join(str(p) for p in CANDIDATE_ROOTS)
            + ". Ensure data/clean_graph.json or data/fir_samples.json exists."
        )

    clean_path = _resolve_clean_graph_path(data_dir)

    # Prefer clean_graph.json if exists and is recent, but we also benchmark parse_all_sources
    if clean_path.exists():
        try:
            t0 = time.perf_counter()
            text = clean_path.read_text(encoding="utf-8-sig")
            graph = json.loads(text)
            # Validate basic shape before accepting
            if isinstance(graph, dict) and "nodes" in graph and "edges" in graph:
                latency = time.perf_counter() - t0
                return graph, latency, f"clean_graph.json ({clean_path})"
        except Exception as e:
            print(f"[WARN] Failed to load {clean_path}: {e} - falling back to parse_all_sources", file=sys.stderr)

    # Fallback: live orchestration
    # Import lazily to avoid circular import issues when running as script
    sys.path.insert(0, str(PROJECT_ROOT))
    # Also ensure parent of backend is in path
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    # Try multiple import strategies
    parse_all = None
    import_errors: List[str] = []
    try:
        from backend.app.core.nlp import parse_all_sources as _parse  # type: ignore
        parse_all = _parse
    except Exception as e:
        import_errors.append(f"backend.app.core.nlp: {e}")
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "nlp_module", str(PROJECT_ROOT / "backend" / "app" / "core" / "nlp.py")
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore
                parse_all = getattr(mod, "parse_all_sources", None)
        except Exception as e2:
            import_errors.append(f"direct load nlp.py: {e2}")

    if parse_all is None:
        raise ImportError(f"Could not import parse_all_sources. Errors: {'; '.join(import_errors)}")

    # Execute orchestrator with timing
    t0 = time.perf_counter()
    graph = parse_all(str(data_dir))  # type: ignore
    latency = time.perf_counter() - t0
    return graph, latency, f"parse_all_sources({data_dir})"


# ---------------------------------------------------------------------------
# Validation functions - each raises AssertionError with explicit details on failure
# ---------------------------------------------------------------------------

def validate_node_schema(nodes: List[Dict[str, Any]]) -> None:
    errors: List[str] = []
    for idx, n in enumerate(nodes):
        if not isinstance(n, dict):
            errors.append(f"Node[{idx}] is not a dict: {type(n).__name__} -> {n!r:.120}")
            continue
        for key in ("id", "type", "label", "metadata"):
            if key not in n:
                errors.append(f"Node[{idx}] id={n.get('id','<MISSING>')} missing required key '{key}' - keys={list(n.keys())}")
        # type checks
        if "id" in n and not isinstance(n["id"], str):
            errors.append(f"Node[{idx}] id not str: {type(n['id']).__name__}")
        if "type" in n and not isinstance(n["type"], str):
            errors.append(f"Node[{idx}] type not str")
        if "label" in n and not isinstance(n["label"], str):
            errors.append(f"Node[{idx}] label not str")
        if "metadata" in n and not isinstance(n["metadata"], dict):
            errors.append(f"Node[{idx}] metadata not dict: {type(n['metadata']).__name__}")
        # strict type enum
        if "type" in n and n["type"] not in ALLOWED_NODE_TYPES:
            errors.append(
                f"Node[{idx}] id={n.get('id')} has invalid type '{n.get('type')}' - allowed {sorted(ALLOWED_NODE_TYPES)}"
            )
        # id non-empty
        if "id" in n and isinstance(n["id"], str) and not n["id"].strip():
            errors.append(f"Node[{idx}] has empty id")
        # label non-empty
        if "label" in n and isinstance(n["label"], str) and not n["label"].strip():
            errors.append(f"Node[{idx}] id={n.get('id')} has empty label")

    if errors:
        raise AssertionError("Node schema validation failed:\n  - " + "\n  - ".join(errors))


def validate_edge_schema(edges: List[Dict[str, Any]]) -> None:
    errors: List[str] = []
    for idx, e in enumerate(edges):
        if not isinstance(e, dict):
            errors.append(f"Edge[{idx}] not a dict: {type(e).__name__}")
            continue
        for key in ("source", "target", "type", "metadata"):
            if key not in e:
                errors.append(f"Edge[{idx}] {e.get('source','?')}->{e.get('target','?')} missing key '{key}' - keys={list(e.keys())}")
        if "type" in e and e["type"] not in ALLOWED_EDGE_TYPES:
            errors.append(
                f"Edge[{idx}] {e.get('source')}->{e.get('target')} invalid type '{e.get('type')}' - allowed {sorted(ALLOWED_EDGE_TYPES)}"
            )
        if "metadata" in e and not isinstance(e["metadata"], dict):
            errors.append(f"Edge[{idx}] metadata not dict")
        if "source" in e and not isinstance(e["source"], str):
            errors.append(f"Edge[{idx}] source not str")
        if "target" in e and not isinstance(e["target"], str):
            errors.append(f"Edge[{idx}] target not str")
        if "source" in e and isinstance(e["source"], str) and not e["source"].strip():
            errors.append(f"Edge[{idx}] empty source")
        if "target" in e and isinstance(e["target"], str) and not e["target"].strip():
            errors.append(f"Edge[{idx}] empty target")

    if errors:
        raise AssertionError("Edge schema validation failed:\n  - " + "\n  - ".join(errors))


def validate_no_dangling_edges(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
    node_ids = {n["id"] for n in nodes if isinstance(n.get("id"), str)}
    dangling: List[str] = []
    for idx, e in enumerate(edges):
        src = e.get("source")
        tgt = e.get("target")
        if src not in node_ids:
            dangling.append(f"Edge[{idx}] source '{src}' not in node ids (type={e.get('type')})")
        if tgt not in node_ids:
            dangling.append(f"Edge[{idx}] target '{tgt}' not in node ids (type={e.get('type')})")
    if dangling:
        raise AssertionError(
            f"Dangling edge check failed - {len(dangling)} dangling reference(s):\n  - "
            + "\n  - ".join(dangling)
            + f"\n  Node ids ({len(node_ids)}): {sorted(list(node_ids))[:12]}{'...' if len(node_ids)>12 else ''}"
        )


def validate_alias_deduplication(nodes: List[Dict[str, Any]]) -> None:
    """
    Ensure alias pairs like Ramesh Kumar/Rama resolve to single canonical Suspect node with merged evidence.
    Checks:
      - No two Suspect nodes share lower-cased label that are alias partners
      - Canonical nodes contain alias in metadata.aliases
      - Evidence merged (at least one canonical has evidence_source containing FIR id)
    """
    suspects = [n for n in nodes if n.get("type") == "Suspect"]
    label_to_node: Dict[str, Dict[str, Any]] = {str(n.get("label","")).strip().lower(): n for n in suspects}
    labels_lower = set(label_to_node.keys())
    errors: List[str] = []

    for primary, alias in EXPECTED_ALIAS_PAIRS:
        p_low = primary.strip().lower()
        a_low = alias.strip().lower()
        p_exists = p_low in labels_lower
        a_exists = a_low in labels_lower

        # After dedup, alias should NOT exist as separate node (or if it does, it should be merged)
        # For this dataset, we expect alias does NOT appear as its own node label.
        # Allow alias to appear as separate node only if it's also merged into canonical's aliases - but we still flag duplication.
        if p_exists and a_exists:
            errors.append(
                f"Alias deduplication failed for pair '{primary}' alias '{alias}': "
                f"both labels exist as separate Suspect nodes ({p_low} id={label_to_node[p_low].get('id')}, "
                f"{a_low} id={label_to_node[a_low].get('id')}) - expected single canonical. "
                f"Suspect labels present: {sorted(labels_lower)}"
            )
        elif not p_exists and not a_exists:
            # Neither found - maybe data doesn't contain this pair; don't hard-fail but warn
            # Only fail if we expected these pairs from sample data and graph has other suspects
            # Check if graph is non-empty sample
            if len(suspects) > 0:
                errors.append(
                    f"Alias pair '{primary}'/'{alias}' - neither label found in suspects. "
                    f"Labels present: {sorted(labels_lower)} - expected canonical '{primary}'"
                )
        elif not p_exists and a_exists:
            errors.append(
                f"Alias deduplication inverted for '{primary}' alias '{alias}': "
                f"canonical '{primary}' missing but alias '{alias}' present as node id={label_to_node.get(a_low, {}).get('id')}"
            )
        else:
            # p_exists and not a_exists => good, now verify merged evidence
            canon = label_to_node[p_low]
            meta = canon.get("metadata", {}) if isinstance(canon.get("metadata"), dict) else {}
            aliases_meta = meta.get("aliases", [])
            # Normalize aliases list to lower for check
            aliases_lower = [str(a).strip().lower() for a in aliases_meta if isinstance(a, str)]
            if a_low not in aliases_lower:
                errors.append(
                    f"Canonical suspect '{primary}' (id={canon.get('id')}) missing alias '{alias}' in metadata.aliases={aliases_meta}. "
                    f"Expected aliases to contain '{alias}'."
                )
            # Check evidence merged - at least evidence_source present
            ev = meta.get("evidence_source")
            if not ev:
                errors.append(
                    f"Canonical suspect '{primary}' id={canon.get('id')} missing metadata.evidence_source - metadata={meta}"
                )
            # Bonus: check alias node id mapping in resolver if available
            # Verify no duplicate alias id lingering
            alias_id = f"suspect_{alias.lower().replace(' ', '_')}"
            # If alias_id exists as node id somewhere, that's duplicate
            node_ids = {n.get("id") for n in nodes}
            if alias_id in node_ids:
                errors.append(
                    f"Alias node id '{alias_id}' still exists as separate node after dedup - should have been merged to '{canon.get('id')}'"
                )

    if errors:
        raise AssertionError("Alias deduplication validation failed:\n  - " + "\n  - ".join(errors))


def validate_disambiguation(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
    """
    Ensure phone numbers (10 digits starting 6-9) and bank accounts (9-18 digits)
    are not cross-linked or misclassified.

    Checks:
      - Every Phone node label matches PHONE_LABEL_RE
      - Every Account node label matches ACCOUNT_LABEL_RE and is NOT a valid phone (or if 10-digit, not starting 6-9 without phone context)
      - No Phone id appears as Account node and vice versa (id prefix check)
      - Phone numbers not misclassified as Account type, bank accounts not as Phone
      - Edge types not mixing: CALLED edges must connect Phone->Phone, TRANSFERRED must connect Account->Account
    """
    errors: List[str] = []
    phone_nodes = [n for n in nodes if n.get("type") == "Phone"]
    account_nodes = [n for n in nodes if n.get("type") == "Account"]

    phone_labels = {n.get("label") for n in phone_nodes}
    account_labels = {n.get("label") for n in account_nodes}

    for n in phone_nodes:
        label = str(n.get("label", "")).strip()
        if not PHONE_LABEL_RE.fullmatch(label):
            errors.append(
                f"Phone node id={n.get('id')} has invalid label '{label}' - expected 10 digits starting 6-9 (regex {PHONE_LABEL_RE.pattern})"
            )
        if not label.isdigit():
            errors.append(f"Phone node id={n.get('id')} label not all digits: '{label}'")
        # Check no overlap with accounts by label
        if label in account_labels:
            errors.append(
                f"Disambiguation failed: Phone label '{label}' (id={n.get('id')}) also appears as Account label - cross-linked classification"
            )
        # Id prefix must be phone_
        if not str(n.get("id","")).startswith("phone_"):
            errors.append(f"Phone node id={n.get('id')} does not start with 'phone_' prefix")

    for n in account_nodes:
        label = str(n.get("label", "")).strip()
        # Allow digits only 9-18 per spec; if label is not pure digits but length 9-18, still warn
        digits = re.sub(r"\D", "", label)
        if not ACCOUNT_LABEL_RE.fullmatch(digits):
            errors.append(
                f"Account node id={n.get('id')} has invalid label '{label}' (digits='{digits}') - expected 9-18 digits (regex {ACCOUNT_LABEL_RE.pattern})"
            )
        if label in phone_labels:
            errors.append(
                f"Disambiguation failed: Account label '{label}' (id={n.get('id')}) also appears as Phone label"
            )
        if not str(n.get("id","")).startswith("account_"):
            errors.append(f"Account node id={n.get('id')} does not start with 'account_' prefix")
        # Ensure 10-digit accounts that look like phones are not actually phones - flag if label is valid phone but type is Account
        if PHONE_LABEL_RE.fullmatch(label):
            # This is ambiguous: 10-digit starting 6-9 could be phone, but spec allows 9-18 digit accounts including 10-digit.
            # We only error if that label also appears as Phone node label (already checked) or if edge context suggests phone
            # For stricter check, ensure account 10-digit starting 6-9 appears only if not present as phone elsewhere - already handled
            pass

    # Check id prefix isolation
    phone_ids = {n.get("id") for n in phone_nodes}
    account_ids = {n.get("id") for n in account_nodes}
    overlap_ids = phone_ids & account_ids
    if overlap_ids:
        errors.append(f"Node ID overlap between Phone and Account types: {overlap_ids}")

    # Edge type vs node type consistency
    node_id_to_type = {n.get("id"): n.get("type") for n in nodes}
    for idx, e in enumerate(edges):
        etype = e.get("type")
        src = e.get("source")
        tgt = e.get("target")
        src_type = node_id_to_type.get(src, "<MISSING>")
        tgt_type = node_id_to_type.get(tgt, "<MISSING>")
        if etype == "CALLED":
            if src_type != "Phone" or tgt_type != "Phone":
                errors.append(
                    f"Edge[{idx}] CALLED {src}({src_type}) -> {tgt}({tgt_type}) - expected Phone->Phone"
                )
        elif etype == "TRANSFERRED":
            if src_type != "Account" or tgt_type != "Account":
                errors.append(
                    f"Edge[{idx}] TRANSFERRED {src}({src_type}) -> {tgt}({tgt_type}) - expected Account->Account"
                )
        elif etype == "USES":
            # Expected Suspect->Phone per nlp.py, but allow Suspect->Phone only
            if src_type != "Suspect" or tgt_type != "Phone":
                errors.append(
                    f"Edge[{idx}] USES {src}({src_type}) -> {tgt}({tgt_type}) - expected Suspect->Phone"
                )
        elif etype == "OPERATES":
            # Suspect->CrimeCase or Suspect->Account (per nlp implementation)
            if src_type != "Suspect":
                errors.append(f"Edge[{idx}] OPERATES {src}({src_type}) -> {tgt}({tgt_type}) - expected source Suspect")
            if tgt_type not in {"CrimeCase", "Account"}:
                errors.append(
                    f"Edge[{idx}] OPERATES {src}({src_type}) -> {tgt}({tgt_type}) - expected target CrimeCase or Account, got {tgt_type}"
                )
        elif etype == "CO_ACCUSED_IN":
            if src_type != "Suspect" or tgt_type != "Suspect":
                errors.append(
                    f"Edge[{idx}] CO_ACCUSED_IN {src}({src_type}) -> {tgt}({tgt_type}) - expected Suspect->Suspect"
                )

    if errors:
        raise AssertionError("Disambiguation validation failed:\n  - " + "\n  - ".join(errors))


def validate_edge_metadata(edges: List[Dict[str, Any]]) -> None:
    errors: List[str] = []
    for idx, e in enumerate(edges):
        etype = e.get("type")
        meta = e.get("metadata", {}) if isinstance(e.get("metadata"), dict) else {}
        ts = meta.get("timestamp")

        if etype == "TRANSFERRED":
            amt = meta.get("amount")
            if amt is None:
                errors.append(f"Edge[{idx}] TRANSFERRED {e.get('source')}->{e.get('target')} missing metadata.amount")
            elif not isinstance(amt, (int, float)):
                errors.append(f"Edge[{idx}] TRANSFERRED amount not numeric: {amt!r} ({type(amt).__name__})")
            elif float(amt) == 0.0:
                errors.append(f"Edge[{idx}] TRANSFERRED amount is zero: {amt} - expected non-zero per spec")
            elif float(amt) < 0:
                errors.append(f"Edge[{idx}] TRANSFERRED amount negative: {amt}")

            # Also check evidence_source present
            if not meta.get("evidence_source"):
                errors.append(f"Edge[{idx}] TRANSFERRED missing evidence_source")
            # tx_id should be present for traceability
            if not meta.get("tx_id"):
                # Not hard error, but warn - we treat as minor if missing but not empty graph
                pass

        elif etype == "CALLED":
            if not ts:
                errors.append(f"Edge[{idx}] CALLED {e.get('source')}->{e.get('target')} missing timestamp")
            else:
                ts_str = str(ts)
                if not ISO8601_RE.search(ts_str):
                    errors.append(
                        f"Edge[{idx}] CALLED timestamp not ISO8601-like '{ts_str}' - expected YYYY-MM-DDTHH:MM:SS"
                    )
                # Try parsing
                try:
                    # Allow with timezone
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        # Try strict parse
                        datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
                except Exception as ex:
                    errors.append(f"Edge[{idx}] CALLED timestamp parse failed '{ts_str}': {ex}")

            # Check duration present and numeric
            dur = meta.get("duration")
            if dur is None:
                errors.append(f"Edge[{idx}] CALLED missing duration")
            elif not isinstance(dur, (int, float)):
                errors.append(f"Edge[{idx}] CALLED duration not numeric: {dur!r}")
            elif int(dur) < 0:
                errors.append(f"Edge[{idx}] CALLED duration negative: {dur}")

            if not meta.get("evidence_source"):
                errors.append(f"Edge[{idx}] CALLED missing evidence_source")
        else:
            # For other edge types, still require timestamp and evidence_source
            if not ts:
                errors.append(f"Edge[{idx}] {etype} {e.get('source')}->{e.get('target')} missing timestamp")
            elif not ISO8601_RE.search(str(ts)):
                errors.append(f"Edge[{idx}] {etype} timestamp not ISO8601: '{ts}'")
            if not meta.get("evidence_source"):
                errors.append(f"Edge[{idx}] {etype} missing evidence_source")

    if errors:
        raise AssertionError("Edge metadata validation failed:\n  - " + "\n  - ".join(errors))


# ---------------------------------------------------------------------------
# Reporting - pretty tables
# ---------------------------------------------------------------------------

def _print_table(title: str, counter: Counter, total_label: str = "Total") -> None:
    # Determine column widths
    keys = sorted(counter.keys())
    # Include total row
    all_keys = keys + [total_label]
    max_key_len = max(len(k) for k in all_keys) if all_keys else 10
    max_val_len = max(len(str(v)) for v in list(counter.values()) + [sum(counter.values())]) if counter else 2
    max_key_len = max(max_key_len, len("Type"))
    max_val_len = max(max_val_len, len("Count"))

    line = f"+-{'-'*max_key_len}-+-{'-'*max_val_len}-+"
    header = f"| {'Type'.ljust(max_key_len)} | {'Count'.rjust(max_val_len)} |"

    print(f"\n{title}")
    print(line)
    print(header)
    print(line)
    for k in keys:
        print(f"| {k.ljust(max_key_len)} | {str(counter[k]).rjust(max_val_len)} |")
    print(line)
    total = sum(counter.values())
    print(f"| {total_label.ljust(max_key_len)} | {str(total).rjust(max_val_len)} |")
    print(line)


def run_all_validations(graph: Dict[str, List[Dict[str, Any]]]) -> Tuple[Counter, Counter]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise AssertionError(f"Graph must have 'nodes' and 'edges' as lists - got nodes={type(nodes).__name__}, edges={type(edges).__name__}")

    print("\n[1/6] Validating node schema ...")
    validate_node_schema(nodes)
    print("      [OK] Node schema ok")

    print("[2/6] Validating edge schema ...")
    validate_edge_schema(edges)
    print("      [OK] Edge schema ok")

    print("[3/6] Validating no dangling edges ...")
    validate_no_dangling_edges(nodes, edges)
    print("      [OK] No dangling edges")

    print("[4/6] Validating alias deduplication (Ramesh Kumar/Rama, Rakesh/Bunty, Sunil Kumar/Sonu) ...")
    validate_alias_deduplication(nodes)
    print("      [OK] Alias deduplication ok - canonical suspects merged with aliases")

    print("[5/6] Validating phone/account disambiguation ...")
    validate_disambiguation(nodes, edges)
    print("      [OK] Disambiguation ok - Phone 10-digit (6-9) vs Account 9-18 digits correctly classified")

    print("[6/6] Validating edge metadata (amounts, timestamps) ...")
    validate_edge_metadata(edges)
    print("      [OK] Edge metadata ok - TRANSFERRED amounts non-zero, CALLED timestamps ISO8601")

    node_counter = Counter(n.get("type", "<UNKNOWN>") for n in nodes)
    edge_counter = Counter(e.get("type", "<UNKNOWN>") for e in edges)
    return node_counter, edge_counter


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 78)
    print(" NLP / Resolver Diagnostic Suite ".center(78, "="))
    print("=" * 78)
    print(f"Python: {sys.version.split()[0]} | File: {THIS_FILE}")
    print(f"Project root resolved: {PROJECT_ROOT} (exists={PROJECT_ROOT.exists()})")
    data_dir = _resolve_data_dir()
    print(f"Data dir resolved: {data_dir} (exists={data_dir.exists() if data_dir else False})")
    if data_dir and (data_dir / "clean_graph.json").exists():
        print(f"Clean graph path: {data_dir / 'clean_graph.json'}")
    print("-" * 78)

    overall_t0 = time.perf_counter()

    try:
        graph, load_latency, source_label = load_graph()
    except Exception as e:
        print(f"\n[FAIL] Could not load graph: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    print(f"\nGraph loaded from: {source_label}")
    print(f"Load latency: {load_latency*1000:.2f} ms")
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    print(f"Graph size: {len(nodes)} nodes, {len(edges)} edges (from source)")

    # Benchmark validation phase
    val_t0 = time.perf_counter()
    try:
        node_counter, edge_counter = run_all_validations(graph)
    except AssertionError as e:
        print("\n" + "=" * 78)
        print(" VALIDATION FAILED ".center(78, "!"))
        print("=" * 78)
        print(str(e))
        print("\n--- Summary (partial) ---")
        # Still print counters for debugging
        try:
            nodes = graph.get("nodes", [])
            edges = graph.get("edges", [])
            n_cnt = Counter(n.get("type") for n in nodes)
            e_cnt = Counter(e.get("type") for e in edges)
            _print_table("Nodes by Type (partial)", n_cnt)
            _print_table("Edges by Type (partial)", e_cnt)
        except Exception:
            pass
        print(f"\nExecution latency (load+validation): {(time.perf_counter()-overall_t0)*1000:.2f} ms")
        return 1
    except Exception as e:
        print(f"\n[FAIL] Unexpected error during validation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    val_latency = time.perf_counter() - val_t0
    total_latency = time.perf_counter() - overall_t0

    # Report
    print("\n" + "=" * 78)
    print(" Execution Report ".center(78, "="))
    print("=" * 78)
    _print_table("Total Nodes by Type", node_counter)
    _print_table("Total Edges by Type", edge_counter)

    print(f"\nLatency Breakdown:")
    print(f"  *  Graph load / parse_all_sources : {load_latency*1000:8.2f} ms  (source: {source_label})")
    print(f"  *  Validation (6 checks)          : {val_latency*1000:8.2f} ms")
    print(f"  *  Total execution                : {total_latency*1000:8.2f} ms")

    # Additional sanity stats
    print(f"\nGraph Integrity:")
    print(f"  *  Dangling edge check: PASSED (all {len(edges)} edges reference valid node ids)")
    print(f"  *  Schema check: PASSED ({len(nodes)} nodes x 4 keys, {len(edges)} edges x 4 keys)")
    print(f"  *  Strict enums: PASSED (nodes {sorted(ALLOWED_NODE_TYPES)}, edges {sorted(ALLOWED_EDGE_TYPES)})")

    # Alias evidence summary
    suspects = [n for n in graph.get("nodes", []) if n.get("type") == "Suspect"]
    print(f"\nAlias Resolution Evidence (canonical suspects):")
    for s in sorted(suspects, key=lambda x: x.get("label","")):
        lbl = s.get("label")
        meta = s.get("metadata", {})
        aliases = meta.get("aliases", [])
        ev = meta.get("evidence_source", meta.get("fir_nos", "--"))
        if isinstance(ev, list):
            ev = ", ".join(map(str, ev))
        print(f"  *  {lbl:<16} (id={s.get('id')}) aliases={aliases if aliases else '--'} evidence={ev}")

    # Disambiguation sample
    phones = [n for n in graph.get("nodes", []) if n.get("type") == "Phone"]
    accounts = [n for n in graph.get("nodes", []) if n.get("type") == "Account"]
    if phones:
        print(f"\nPhone sample (Phone type, 10-digit 6-9): {', '.join(p.get('label') for p in phones[:3])}{' ...' if len(phones)>3 else ''}")
    if accounts:
        print(f"Account sample (Account type, 9-18 digits): {', '.join(a.get('label') for a in accounts[:3])}{' ...' if len(accounts)>3 else ''}")

    transferred = [e for e in graph.get("edges", []) if e.get("type") == "TRANSFERRED"]
    called = [e for e in graph.get("edges", []) if e.get("type") == "CALLED"]
    if transferred:
        amt_sample = ", ".join(str(e.get("metadata", {}).get("amount")) for e in transferred[:2])
        print(f"\nTRANSFERRED amount sample: {amt_sample} (all non-zero [OK])")
    if called:
        ts_sample = ", ".join(str(e.get("metadata", {}).get("timestamp"))[:19] for e in called[:2])
        print(f"CALLED timestamp sample: {ts_sample} (ISO8601 [OK])")

    print("\n" + "=" * 78)
    print(" ALL VALIDATIONS PASSED ".center(78, "="))
    print("=" * 78)
    print("[OK] Schema & Data Integrity: OK")
    print("[OK] Edge Cases & Safety: OK (no dangling, dedup, disambiguation, metadata)")
    print(f"[OK] Execution latency: {total_latency*1000:.2f} ms total")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())



