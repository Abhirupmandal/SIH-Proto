"""
backend/app/core/resolver.py
Entity deduplication and phonetic matching for Suspect nodes.

- Merges alias variations (e.g., "Rakesh alias Bunty", "Ramesh Kumar" vs "Rama") into canonical suspect nodes.
- Uses jellyfish (soundex/metaphone/jaro_winkler) with difflib fallback for phonetic/fuzzy matching.
- Maintains internal lookup maps so alias node IDs map to primary Suspect ID for edge remapping.
- Exposes `resolve_suspect_aliases(raw_nodes, alias_map)` and master orchestrator `parse_all_sources`.

Production-grade: type hints, DSU clustering, threshold tuning, graceful fallback when jellyfish unavailable.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional phonetic libraries – graceful fallback chain
# ---------------------------------------------------------------------------
try:
    import jellyfish  # type: ignore

    _JELLYFISH_AVAILABLE = True
except ImportError:
    jellyfish = None  # type: ignore
    _JELLYFISH_AVAILABLE = False
    logger.warning("jellyfish not installed – phonetic matching will use difflib only.")

import difflib

# ---------------------------------------------------------------------------
# Global lookup maps – exposed for orchestrator edge remapping
# ---------------------------------------------------------------------------
# Maps lower alias string -> canonical primary string (label lower -> canonical label lower)
ALIAS_LOOKUP: Dict[str, str] = {}
# Maps old node ID (alias sanitized) -> canonical node ID
ALIAS_ID_MAP: Dict[str, str] = {}
# Alias for internal use (underscore-prefixed variant expected by nlp.py)
_ALIAS_ID_MAP: Dict[str, str] = ALIAS_ID_MAP


def _sanitize_id(raw: str) -> str:
    raw = raw.strip().lower()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw or "unknown"


def _normalize_name(name: str) -> str:
    """Normalize suspect name for comparison: lowercase, collapse spaces, strip titles."""
    if not isinstance(name, str):
        name = str(name)
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.strip().lower()
    # Remove honorifics / prefixes
    name = re.sub(r"\b(s\/o|d\/o|mr\.?|mrs\.?|ms\.?|shri|sri)\b", "", name)
    name = re.sub(r"[^a-z\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _soundex_code(name: str) -> str:
    """Return soundex code for first token or full name; fallback to first char if unavailable."""
    if not name:
        return ""
    token = _normalize_name(name).split()[0] if _normalize_name(name) else name
    if _JELLYFISH_AVAILABLE:
        try:
            return jellyfish.soundex(token)  # type: ignore
        except Exception:
            pass
    # Fallback: simple first-char + length heuristic
    return token[0] + str(len(token)) if token else ""


def _metaphone_code(name: str) -> str:
    if not _JELLYFISH_AVAILABLE:
        return _normalize_name(name)
    try:
        # jellyfish.metaphone returns single code
        return jellyfish.metaphone(name)  # type: ignore
    except Exception:
        try:
            return jellyfish.metaphone(_normalize_name(name))  # type: ignore
        except Exception:
            return _normalize_name(name)


def _jaro_winkler(a: str, b: str) -> float:
    na = _normalize_name(a)
    nb = _normalize_name(b)
    if not na or not nb:
        return 0.0
    if _JELLYFISH_AVAILABLE:
        try:
            return float(jellyfish.jaro_winkler_similarity(na, nb))  # type: ignore
        except Exception:
            pass
    # difflib fallback
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _phonetic_match(name_a: str, name_b: str) -> bool:
    """Check whether two names share phonetic code (soundex or metaphone)."""
    if not name_a or not name_b:
        return False
    na = _normalize_name(name_a)
    nb = _normalize_name(name_b)
    # Compare soundex of each token
    tokens_a = na.split()
    tokens_b = nb.split()
    if not tokens_a or not tokens_b:
        return False
    # If any token soundex matches, consider phonetic match
    for ta in tokens_a:
        code_a = _soundex_code(ta)
        for tb in tokens_b:
            code_b = _soundex_code(tb)
            if code_a and code_b and code_a == code_b:
                return True
    # Also try full-name metaphone
    if _JELLYFISH_AVAILABLE:
        try:
            meta_a = _metaphone_code(na)
            meta_b = _metaphone_code(nb)
            if meta_a and meta_b and meta_a == meta_b:
                return True
        except Exception:
            pass
    return False


def _similarity_score(name_a: str, name_b: str) -> float:
    """
    Combined similarity: weighted jaro_winkler + phonetic bonus.
    Returns 0.0-1.0
    """
    jw = _jaro_winkler(name_a, name_b)
    phonetic_bonus = 0.08 if _phonetic_match(name_a, name_b) else 0.0
    # Token overlap bonus: share at least one token exactly?
    tokens_a = set(_normalize_name(name_a).split())
    tokens_b = set(_normalize_name(name_b).split())
    overlap = len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1)
    overlap_bonus = overlap * 0.10
    score = min(1.0, jw + phonetic_bonus + overlap_bonus)
    # If one name is substring of the other (e.g., "Ramesh Kumar" vs "Ramesh"), boost
    na = _normalize_name(name_a)
    nb = _normalize_name(name_b)
    if na in nb or nb in na:
        score = max(score, 0.88)
    return score


# ---------------------------------------------------------------------------
# Union-Find DSU for clustering
# ---------------------------------------------------------------------------

class _DSU:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            self.parent[rx] = ry
        elif self.rank[rx] > self.rank[ry]:
            self.parent[ry] = rx
        else:
            self.parent[ry] = rx
            self.rank[rx] += 1


# ---------------------------------------------------------------------------
# Core resolver
# ---------------------------------------------------------------------------

def get_alias_lookup() -> Dict[str, str]:
    """Return copy of lower-alias -> canonical label map."""
    return dict(ALIAS_LOOKUP)


def get_alias_id_map() -> Dict[str, str]:
    """Return copy of old node ID -> canonical node ID map for edge remapping."""
    return dict(ALIAS_ID_MAP)


def resolve_suspect_aliases(
    raw_nodes: List[Dict[str, Any]],
    alias_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Consolidates duplicate suspect nodes and prepares alias lookup maps.

    Args:
        raw_nodes: Full graph nodes (all types). Only `Suspect` nodes are deduplicated;
                   other types (Phone, Account, Location, CrimeCase) are passed through
                   with ID-level deduplication.
        alias_map: Mapping alias -> primary. Keys/values are case-insensitive name strings.
                   Example: {"bunty": "Rakesh", "rama": "Ramesh Kumar"}.
                   May be empty – in which case phonetic/fuzzy clustering is used solely.

    Returns:
        List[Dict] – deduplicated nodes. Suspect clusters are merged into canonical nodes
                     with aggregated metadata (aliases, evidence_sources, fir_nos).

    Side-effects:
        Populates global `ALIAS_LOOKUP` and `ALIAS_ID_MAP` for caller to remap edges:
            ALIAS_LOOKUP[alias_lower] = canonical_label_lower
            ALIAS_ID_MAP[old_suspect_id] = canonical_suspect_id
    """
    # Reset globals
    ALIAS_LOOKUP.clear()
    ALIAS_ID_MAP.clear()
    _ALIAS_ID_MAP.clear()

    if not isinstance(raw_nodes, list):
        logger.warning("raw_nodes is not a list – returning empty")
        return []
    if alias_map is None:
        alias_map = {}
    if not isinstance(alias_map, dict):
        logger.warning("alias_map is not a dict – ignoring: %r", alias_map)
        alias_map = {}

    # Normalize alias_map to lower -> original primary casing
    normalized_alias_map: Dict[str, str] = {}
    for k, v in alias_map.items():
        if k is None or v is None:
            continue
        k_str = str(k).strip()
        v_str = str(v).strip()
        if not k_str or not v_str:
            continue
        # Map alias lower -> primary (preserve primary original casing for label)
        normalized_alias_map[k_str.lower()] = v_str
        # Also ensure primary maps to itself for DSU
        # We will not overwrite if already maps elsewhere – keep first
        if v_str.lower() not in normalized_alias_map:
            normalized_alias_map[v_str.lower()] = v_str

    # Separate suspect nodes vs others
    suspect_indices: List[int] = []
    suspect_nodes: List[Dict[str, Any]] = []
    other_nodes: List[Dict[str, Any]] = []

    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        ntype = node.get("type")
        if ntype == "Suspect":
            suspect_indices.append(len(other_nodes) + len(suspect_nodes))  # not needed but track
            suspect_nodes.append(node)
        else:
            other_nodes.append(node)

    if not suspect_nodes:
        # No suspects to resolve – just deduplicate other nodes by ID and return
        deduped = _dedup_other_nodes(other_nodes)
        logger.info("No suspect nodes to resolve – returning %d other nodes", len(deduped))
        return deduped

    n = len(suspect_nodes)
    dsu = _DSU(n)

    # Build name -> index map (lower normalized -> list of indices)
    norm_name_to_indices: Dict[str, List[int]] = {}
    for idx, node in enumerate(suspect_nodes):
        label = str(node.get("label", "")).strip()
        norm = _normalize_name(label)
        # Also consider alias list inside metadata as alternate names that should union
        norm_name_to_indices.setdefault(norm, []).append(idx)
        # Additionally map raw lower label
        raw_lower = label.strip().lower()
        if raw_lower != norm:
            norm_name_to_indices.setdefault(raw_lower, []).append(idx)

    # Helper: find index for a name (exact or normalized) – returns first match or None
    def _find_indices_for_name(name_lower: str) -> List[int]:
        norm = _normalize_name(name_lower)
        candidates: List[int] = []
        if norm in norm_name_to_indices:
            candidates.extend(norm_name_to_indices[norm])
        if name_lower in norm_name_to_indices:
            candidates.extend(norm_name_to_indices[name_lower])
        # Also try soundex-fuzzy fallback search brute force
        return list(set(candidates))

    # Step 1: Union explicit alias mappings
    for alias_lower, primary in normalized_alias_map.items():
        primary_lower = primary.strip().lower()
        alias_indices = _find_indices_for_name(alias_lower)
        primary_indices = _find_indices_for_name(primary_lower)

        # If neither alias nor primary exists as node, skip – but record lookup for future nodes (e.g., CDR phones? ignore)
        # If only alias exists (alias node exists but primary does not), we still want to keep alias node as its own cluster
        # but record mapping alias -> primary for edge remapping to primary id (which may be synthesized later).
        if alias_indices and primary_indices:
            # Union all alias nodes with all primary nodes (transitive)
            for ai in alias_indices:
                for pi in primary_indices:
                    dsu.union(ai, pi)
        elif alias_indices and not primary_indices:
            # Alias exists, primary missing – we still treat alias node's canonical as primary string
            # No DSU union needed (single cluster), but will set lookup later.
            pass
        elif not alias_indices and primary_indices:
            # Primary exists but alias does not – nothing to union; still record lookup for any future alias id
            pass

        # Record lookup regardless (for edge remapping)
        # ALIAS_LOOKUP uses lower alias -> lower primary canonical
        ALIAS_LOOKUP[alias_lower] = primary_lower

    # Step 2: Phonetic / fuzzy clustering among suspect nodes
    # Thresholds: tuned for Indian names – 0.88 jaro_winkler + phonetic or token overlap
    FUZZY_THRESHOLD = 0.88
    PHONETIC_THRESHOLD = 0.82  # lower if phonetic matches

    # To avoid O(n^2) for large n (>500) we could use blocking by soundex, but n is typically small (<200) so full pairwise is ok.
    for i in range(n):
        label_i = str(suspect_nodes[i].get("label", ""))
        norm_i = _normalize_name(label_i)
        if not norm_i:
            continue
        for j in range(i + 1, n):
            # Skip if already united via alias map
            if dsu.find(i) == dsu.find(j):
                continue
            label_j = str(suspect_nodes[j].get("label", ""))
            norm_j = _normalize_name(label_j)
            if not norm_j:
                continue

            # Quick exact or case-insensitive match
            if norm_i == norm_j:
                dsu.union(i, j)
                continue

            # Token-exact match boost: share first name exact
            tokens_i = norm_i.split()
            tokens_j = norm_j.split()
            share_first = tokens_i and tokens_j and tokens_i[0] == tokens_j[0]

            score = _similarity_score(label_i, label_j)
            # Determine effective threshold
            effective_threshold = PHONETIC_THRESHOLD if _phonetic_match(label_i, label_j) or share_first else FUZZY_THRESHOLD

            # Special handling for short aliases like "Bunty" vs "Rakesh" – those won't score high, but explicit alias map already handled.
            # For unmapped short names (single token, length <=6), require alias map to merge – do not merge on phonetic alone.
            is_short_single_token = (len(tokens_i) == 1 and len(tokens_i[0]) <= 6) or (len(tokens_j) == 1 and len(tokens_j[0]) <= 6)
            if is_short_single_token and not _phonetic_match(label_i, label_j):
                # Skip fuzzy merge for short nicknames unless explicit alias map – prevents over-merging distinct short names
                continue

            if score >= effective_threshold:
                # Additional guard: avoid merging names that share no phonetic or token overlap and are long distinct
                # e.g., "Ramesh Kumar" vs "Suresh Kumar" share last name but first token different – should we merge? No.
                # Require either first token match or phonetic match or high score >0.92 for last-name-only overlap.
                if tokens_i and tokens_j:
                    first_i, last_i = tokens_i[0], tokens_i[-1] if len(tokens_i) > 1 else tokens_i[0]
                    first_j, last_j = tokens_j[0], tokens_j[-1] if len(tokens_j) > 1 else tokens_j[0]
                    # If only last name matches but first differs substantially, need higher threshold
                    if first_i != first_j and last_i == last_j and score < 0.92:
                        continue
                dsu.union(i, j)
                logger.debug("Fuzzy union: '%s' <-> '%s' score %.3f", label_i, label_j, score)

    # Step 3: Build clusters
    clusters: Dict[int, List[int]] = {}
    for idx in range(n):
        root = dsu.find(idx)
        clusters.setdefault(root, []).append(idx)

    canonical_nodes: List[Dict[str, Any]] = []
    # Keep track of which original suspect IDs map to which canonical ID
    for root, members in clusters.items():
        # Decide canonical member: longest label (most descriptive) or earliest with most metadata
        # Sort by: label token count desc, label length desc, evidence count desc, original order
        def _canon_rank(idx: int):
            node = suspect_nodes[idx]
            label = str(node.get("label", ""))
            meta = node.get("metadata", {}) or {}
            alias_cnt = len(meta.get("aliases", []) or [])
            # Prefer node whose label is a known primary in alias_map
            is_primary = 1 if label.strip().lower() in {v.lower() for v in normalized_alias_map.values()} else 0
            return (is_primary, len(label.split()), len(label), alias_cnt, -idx)

        members_sorted = sorted(members, key=_canon_rank, reverse=True)
        canonical_idx = members_sorted[0]
        canonical_node = suspect_nodes[canonical_idx]
        canonical_label = str(canonical_node.get("label", "")).strip()
        canonical_id = str(canonical_node.get("id", f"suspect_{_sanitize_id(canonical_label.lower())}"))
        # Ensure canonical ID follows sanitized convention – keep original if present else generate
        if not canonical_id:
            canonical_id = f"suspect_{_sanitize_id(canonical_label.lower())}"

        # Aggregate metadata across cluster
        merged_aliases: List[str] = []
        merged_evidence_sources: List[str] = []
        merged_fir_nos: List[str] = []
        merged_so_relations: List[Dict[str, str]] = []
        merged_vehicles: List[str] = []
        merged_metadata: Dict[str, Any] = {}

        # Start from canonical metadata copy
        base_meta = dict(canonical_node.get("metadata", {}) or {})
        # Initialize collections from base
        for m in members:
            node = suspect_nodes[m]
            label = str(node.get("label", "")).strip()
            meta = node.get("metadata", {}) or {}
            # Collect alias strings: node's own label if not canonical, plus its alias list
            if m != canonical_idx:
                if label.lower() != canonical_label.lower() and label not in merged_aliases:
                    merged_aliases.append(label)
            for a in meta.get("aliases", []) or []:
                if isinstance(a, str) and a and a not in merged_aliases and a.lower() != canonical_label.lower():
                    merged_aliases.append(a)
            # Collect evidence sources
            ev = meta.get("evidence_source")
            if ev:
                if isinstance(ev, list):
                    for e in ev:
                        if e not in merged_evidence_sources:
                            merged_evidence_sources.append(e)
                elif isinstance(ev, str) and ev not in merged_evidence_sources:
                    merged_evidence_sources.append(ev)
            # Also top-level evidence_source in node? handled
            fir_no = meta.get("fir_no") or meta.get("FIR_no")
            if fir_no and fir_no not in merged_fir_nos:
                if isinstance(fir_no, list):
                    for f in fir_no:
                        if f not in merged_fir_nos:
                            merged_fir_nos.append(f)
                elif isinstance(fir_no, str) and fir_no not in merged_fir_nos:
                    merged_fir_nos.append(fir_no)
            # s/o relations
            for rel in meta.get("so_relations", []) or []:
                if rel not in merged_so_relations:
                    merged_so_relations.append(rel)
            # vehicles
            for v in meta.get("vehicles", []) or []:
                if v not in merged_vehicles:
                    merged_vehicles.append(v)
            # Merge any other metadata keys (ps_name etc) – keep canonical's value, but collect lists for multi-valued
            for k, v in meta.items():
                if k in {"aliases", "evidence_source", "fir_no", "FIR_no", "so_relations", "vehicles"}:
                    continue
                if k not in merged_metadata:
                    merged_metadata[k] = v
                elif isinstance(merged_metadata[k], list) and isinstance(v, list):
                    for item in v:
                        if item not in merged_metadata[k]:
                            merged_metadata[k].append(item)
                elif merged_metadata[k] != v:
                    # Convert to list if conflict
                    if not isinstance(merged_metadata[k], list):
                        merged_metadata[k] = [merged_metadata[k]]
                    if v not in merged_metadata[k]:
                        if isinstance(v, list):
                            merged_metadata[k].extend([x for x in v if x not in merged_metadata[k]])
                        else:
                            merged_metadata[k].append(v)

        # Build final merged metadata
        final_meta: Dict[str, Any] = {}
        # Start with base_meta keys
        for k, v in base_meta.items():
            if k not in {"aliases", "evidence_source", "fir_no", "so_relations", "vehicles"}:
                final_meta[k] = v
        # Add merged extras
        for k, v in merged_metadata.items():
            if k not in final_meta:
                final_meta[k] = v

        if merged_aliases:
            # Deduplicate aliases case-insensitively, preserve original casing from first occurrence
            # Also include any base aliases not yet added
            base_aliases = base_meta.get("aliases", []) or []
            all_aliases = []
            seen_lower = set()
            for a in list(base_aliases) + merged_aliases:
                if not isinstance(a, str):
                    continue
                low = a.strip().lower()
                if low and low != canonical_label.lower() and low not in seen_lower:
                    seen_lower.add(low)
                    all_aliases.append(a.strip())
            final_meta["aliases"] = all_aliases
        else:
            # Preserve base aliases if any
            if base_meta.get("aliases"):
                final_meta["aliases"] = base_meta["aliases"]

        if merged_evidence_sources:
            # Merge with base evidence_source if present
            base_ev = base_meta.get("evidence_source")
            all_ev = []
            if base_ev:
                if isinstance(base_ev, list):
                    all_ev.extend(base_ev)
                elif isinstance(base_ev, str):
                    all_ev.append(base_ev)
            for e in merged_evidence_sources:
                if e not in all_ev:
                    all_ev.append(e)
            # Keep as list if multiple else string? Spec metadata can be {...} – keep string if single else list
            final_meta["evidence_source"] = all_ev[0] if len(all_ev) == 1 else all_ev
        elif base_meta.get("evidence_source"):
            final_meta["evidence_source"] = base_meta["evidence_source"]

        if merged_fir_nos:
            final_meta["fir_nos"] = merged_fir_nos
            # Preserve singular fir_no as canonical first
            if "fir_no" not in final_meta and merged_fir_nos:
                final_meta["fir_no"] = merged_fir_nos[0]

        if merged_so_relations:
            final_meta["so_relations"] = merged_so_relations
        if merged_vehicles:
            final_meta["vehicles"] = merged_vehicles

        # Ensure canonical node has correct id/type/label/metadata
        new_canonical: Dict[str, Any] = {
            "id": canonical_id,
            "type": "Suspect",
            "label": canonical_label,
            "metadata": final_meta,
        }
        canonical_nodes.append(new_canonical)

        # Populate alias maps for edge remapping
        canonical_label_lower = canonical_label.strip().lower()
        canonical_aliases_lower = {canonical_label_lower}
        for alias in final_meta.get("aliases", []) or []:
            if isinstance(alias, str):
                canonical_aliases_lower.add(alias.strip().lower())

        # For each member, map its original ID -> canonical ID
        for m in members:
            orig_node = suspect_nodes[m]
            orig_id = str(orig_node.get("id", f"suspect_{_sanitize_id(str(orig_node.get('label','')).lower())}"))
            if orig_id != canonical_id:
                ALIAS_ID_MAP[orig_id] = canonical_id
                _ALIAS_ID_MAP[orig_id] = canonical_id
            orig_label_lower = str(orig_node.get("label", "")).strip().lower()
            if orig_label_lower != canonical_label_lower:
                ALIAS_LOOKUP[orig_label_lower] = canonical_label_lower
                # Also map sanitized ID for alias string itself
                alias_sanitized_id = f"suspect_{_sanitize_id(orig_label_lower)}"
                if alias_sanitized_id != canonical_id:
                    ALIAS_ID_MAP[alias_sanitized_id] = canonical_id
                    _ALIAS_ID_MAP[alias_sanitized_id] = canonical_id

        # Also map each merged alias string lower -> canonical lower, and its sanitized ID
        for alias in final_meta.get("aliases", []) or []:
            if not isinstance(alias, str):
                continue
            alias_lower = alias.strip().lower()
            ALIAS_LOOKUP[alias_lower] = canonical_label_lower
            alias_id = f"suspect_{_sanitize_id(alias_lower)}"
            if alias_id != canonical_id and alias_id not in ALIAS_ID_MAP:
                ALIAS_ID_MAP[alias_id] = canonical_id
                _ALIAS_ID_MAP[alias_id] = canonical_id

        # Also handle explicit alias_map entries that point to this canonical
        for alias_lower, primary_lower in list(normalized_alias_map.items()):
            # primary_lower is raw primary string lower; need to compare to canonical
            if _normalize_name(primary_lower) == _normalize_name(canonical_label_lower) or primary_lower == canonical_label_lower:
                # alias_lower maps to this canonical
                ALIAS_LOOKUP[alias_lower] = canonical_label_lower
                alias_id = f"suspect_{_sanitize_id(alias_lower)}"
                if alias_id != canonical_id:
                    ALIAS_ID_MAP[alias_id] = canonical_id
                    _ALIAS_ID_MAP[alias_id] = canonical_id

    # Include any explicit alias map entries not yet covered (aliases without any node)
    for alias_lower, primary in normalized_alias_map.items():
        primary_lower = primary.strip().lower()
        # If primary already has canonical, ensure alias lookup points there, even if alias node never existed
        # Find canonical id via label mapping
        canon_id_for_primary = None
        for cn in canonical_nodes:
            if cn["label"].strip().lower() == primary_lower or _normalize_name(cn["label"]) == _normalize_name(primary):
                canon_id_for_primary = cn["id"]
                break
        if canon_id_for_primary:
            if alias_lower not in ALIAS_LOOKUP:
                ALIAS_LOOKUP[alias_lower] = primary_lower
            alias_id = f"suspect_{_sanitize_id(alias_lower)}"
            if alias_id != canon_id_for_primary and alias_id not in ALIAS_ID_MAP:
                ALIAS_ID_MAP[alias_id] = canon_id_for_primary
                _ALIAS_ID_MAP[alias_id] = canon_id_for_primary

    # Deduplicate other nodes
    deduped_others = _dedup_other_nodes(other_nodes)

    result = deduped_others + canonical_nodes
    logger.info("Resolver: %d raw suspects clustered into %d canonical suspects across %d clusters", n, len(canonical_nodes), len(clusters))
    logger.debug("Alias lookup samples: %s", dict(list(ALIAS_LOOKUP.items())[:5]))
    logger.debug("Alias ID map samples: %s", dict(list(ALIAS_ID_MAP.items())[:5]))
    return result


def _dedup_other_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate non-suspect nodes by ID, merging metadata."""
    seen: Dict[str, Dict[str, Any]] = {}
    for n in nodes:
        nid = n.get("id")
        if not nid:
            continue
        if nid not in seen:
            seen[nid] = n
        else:
            # Merge metadata
            existing_meta = seen[nid].setdefault("metadata", {})
            new_meta = n.get("metadata", {}) or {}
            for k, v in new_meta.items():
                if k not in existing_meta:
                    existing_meta[k] = v
                elif isinstance(existing_meta[k], list) and isinstance(v, list):
                    for item in v:
                        if item not in existing_meta[k]:
                            existing_meta[k].append(item)
                elif isinstance(existing_meta[k], list):
                    if v not in existing_meta[k]:
                        existing_meta[k].append(v)
                elif existing_meta[k] != v:
                    # Promote to list on conflict
                    if not isinstance(existing_meta[k], list):
                        existing_meta[k] = [existing_meta[k]]
                    if isinstance(v, list):
                        for item in v:
                            if item not in existing_meta[k]:
                                existing_meta[k].append(item)
                    elif v not in existing_meta[k]:
                        existing_meta[k].append(v)
    return list(seen.values())


# ---------------------------------------------------------------------------
# Unified orchestrator – thin wrapper around nlp.parse_all_sources to satisfy
# "Expose a master orchestrator function in nlp.py (or resolver.py)" contract.
# Keeps import local to avoid circular init issues.
# ---------------------------------------------------------------------------

def parse_all_sources(data_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Master orchestrator exposed from resolver.py (delegates to nlp.parse_all_sources).

    Reads:
        {data_dir}/fir_samples.json
        {data_dir}/cdr_tower_dump.csv
        {data_dir}/bank_transactions.csv

    Returns:
        {"nodes": [...], "edges": [...] } per unified schema.
    """
    # Local import to avoid circular dependency at module import time
    try:
        from .nlp import parse_all_sources as _nlp_parse_all  # type: ignore
    except ImportError:
        from backend.app.core.nlp import parse_all_sources as _nlp_parse_all  # type: ignore
    return _nlp_parse_all(data_dir)  # type: ignore


__all__ = [
    "resolve_suspect_aliases",
    "get_alias_lookup",
    "get_alias_id_map",
    "parse_all_sources",
    "ALIAS_LOOKUP",
    "ALIAS_ID_MAP",
]
