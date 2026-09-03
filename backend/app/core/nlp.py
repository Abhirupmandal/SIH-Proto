"""
backend/app/core/nlp.py
Ingestion engine for AI-Powered Criminal Network Analysis System (SIH26189).

- Initializes spaCy `en_core_web_sm` alongside regex patterns for Indian law enforcement records.
- Extracts entities: Suspect names (PERSON via spaCy + alias regex), Indian phones, vehicles, bank accounts, FIR IDs.
- Parses FIR JSON, CDR tower dump CSV, Bank transaction CSV into graph nodes/edges.
- Exposes unified orchestrator `parse_all_sources(data_dir)` returning clean {nodes, edges} schema.

Production-grade: type hints, graceful NaN/missing handling, logging, fallback tokenizers.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ---------------------------------------------------------------------------
# Lazy imports – optional deps handled gracefully
# ---------------------------------------------------------------------------
try:
    import spacy  # type: ignore
    _SPACY_AVAILABLE = True
except ImportError:
    spacy = None  # type: ignore
    _SPACY_AVAILABLE = False
    logger.warning("spaCy not installed – PERSON extraction will fall back to regex heuristics.")

try:
    import pandas as pd  # type: ignore
    _PANDAS_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore
    _PANDAS_AVAILABLE = False

# Import resolver lazily inside functions to avoid circular imports at module load.

# ---------------------------------------------------------------------------
# Regex patterns – Indian law enforcement records
# ---------------------------------------------------------------------------
# Indian mobile: optional +91 / 0 / 00 prefix, then 10-digit starting 6-9
PHONE_RE = re.compile(r"(?:(?:\+|0{0,2})91[\s-]*)?[6-9]\d{9}")

# Indian vehicle plates: e.g., MH12AB1234, DL01C0001, KA05MJ1234
# Spec: [A-Z]{2}\d{1,2}[A-Z]{1,2}\d{4}  – use word boundaries & uppercase
VEHICLE_RE = re.compile(r"\b[A-Z]{2}\d{1,2}[A-Z]{1,2}\d{4}\b")

# Bank accounts: 9-18 digit strings – but will be filtered to exclude phones
BANK_RE = re.compile(r"\b\d{9,18}\b")

# FIR IDs: FIR-YYYY-ALPHANUM
FIR_RE = re.compile(r"\bFIR-\d{4}-[A-Z0-9]+\b")

# Alias variations: strict name pattern to avoid overcapture
# Primary and alias are 1-3 capitalized words; alias keyword case-insensitive
ALIAS_RE = re.compile(
    r"(?P<primary>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(?i:alias|aka|@)\s+(?P<alias>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"
)

# Inline flexible alias pattern for fallback scans – still uses strict name capture but allows preceding context
ALIAS_INLINE_RE = re.compile(
    r"(?P<primary>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(?i:alias|aka|@)\s+(?P<alias>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"
)

# s/o pattern: "Ramesh Kumar s/o Suresh Kumar" – indicates father relation, also alias hint
SO_RE = re.compile(
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+s/o\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",
    re.IGNORECASE,
)

# Fallback PERSON-like regex when spaCy unavailable: capitalised words, heuristic
_FALLBACK_PERSON_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b")

# ---------------------------------------------------------------------------
# spaCy singleton
# ---------------------------------------------------------------------------
_NLP = None  # cached Language object


def _get_nlp():
    """Lazy-load spaCy en_core_web_sm; falls back to blank English model."""
    global _NLP
    if _NLP is not None:
        return _NLP
    if not _SPACY_AVAILABLE:
        _NLP = None
        return None
    try:
        _NLP = spacy.load("en_core_web_sm")  # type: ignore
        logger.info("Loaded spaCy model en_core_web_sm")
    except OSError as e:
        logger.warning("en_core_web_sm not found (%s) – attempting blank 'en' model as fallback", e)
        try:
            _NLP = spacy.blank("en")  # type: ignore
            # Add sentencizer for basic pipeline if blank
            if "sentencizer" not in _NLP.pipe_names:  # type: ignore
                _NLP.add_pipe("sentencizer")  # type: ignore
        except Exception as e2:
            logger.error("Failed to load blank spaCy model: %s", e2)
            _NLP = None
    return _NLP


# ---------------------------------------------------------------------------
# Helpers – sanitization & normalization
# ---------------------------------------------------------------------------

def _sanitize_id(raw: str) -> str:
    """Convert arbitrary string to safe node-id slug."""
    raw = raw.strip().lower()
    # Normalize unicode
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    # Replace non-alnum with underscore, collapse
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    if not raw:
        raw = hashlib.md5(raw.encode()).hexdigest()[:8]
    return raw


def _normalize_phone(raw: str) -> str:
    """Strip Indian country code / separators and return last 10 digits if valid."""
    digits = re.sub(r"\D", "", raw)
    # Handle +91 or 091 prefix – keep last 10 digits if length >10 and starts with 91
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    elif len(digits) > 10 and digits.startswith("0"):
        digits = digits.lstrip("0")[-10:]
    return digits


def _is_valid_phone(phone_digits: str) -> bool:
    return len(phone_digits) == 10 and phone_digits[0] in "6789"


def _normalize_timestamp(value: Any) -> str:
    """Try to coerce various timestamp formats to ISO-8601 UTC string."""
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return datetime.now(timezone.utc).isoformat()
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null", "nat"}:
        return datetime.now(timezone.utc).isoformat()
    # Try common formats
    fmts = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    # Fallback: pandas parsing if available
    if _PANDAS_AVAILABLE:
        try:
            dt = pd.to_datetime(s, utc=True, errors="coerce")  # type: ignore
            if pd.notna(dt):  # type: ignore
                return dt.isoformat()  # type: ignore
        except Exception:
            pass
    # dateutil fallback attempt
    try:
        from dateutil import parser as date_parser  # type: ignore

        dt = date_parser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    # Last resort: return as-is but ensure string
    return s


def _safe_str(value: Any, default: str = "") -> str:
    """Coerce CSV cell value to stripped string; handles NaN/None gracefully."""
    if value is None:
        return default
    # pandas NaN check
    if _PANDAS_AVAILABLE:
        try:
            if pd.isna(value):  # type: ignore
                return default
        except Exception:
            pass
    # float NaN
    if isinstance(value, float) and (value != value):  # NaN check
        return default
    s = str(value).strip()
    if s.lower() in {"nan", "none", "null", "nat", ""}:
        return default
    return s


def _dedup_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        key = x.strip().lower() if isinstance(x, str) else x
        if key not in seen and key:
            seen.add(key)
            out.append(x)
    return out


# Stopwords that should be stripped from start of a captured PERSON / alias
_PERSON_PREFIX_STOPWORDS = {
    "suspect", "accused", "alias", "aka", "@", "mr", "mrs", "ms", "shri", "sri",
    "s/o", "d/o", "s", "o", "so"
}
_PERSON_NOISE_EXACT = {
    "fir", "police station", "district", "unknown", "police", "station", "ps", "ipc", "crpc",
    "andheri",
    "both", "they", "them", "he", "she", "it", "we", "you", "this", "that", "these", "those",
    "his", "her", "their", "our", "your", "accused", "suspect", "victim", "complainant",
}
# Tokens that indicate a name is actually a PS / location, not a person
_LOCATION_HINTS = {"ps", "police", "station", "district", "colony", "nagar", "marg", "road", "thana"}
# Lower verbs that should not appear in a person/alias name
_NON_NAME_VERBS = {
    "was", "were", "is", "are", "being", "been", "had", "has", "have",
    "found", "arrested", "using", "along", "with", "using", "contact", "phone",
}

# More precise s/o pattern: capture only proper-cased names, s/o token case-insensitive
SO_RE_STRICT = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?i:s/o)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b"
)


def _clean_person_name(raw: str) -> str:
    """Strip leading law-enforcement keywords and truncate to plausible person name."""
    if not raw:
        return ""
    name = re.sub(r"\s+", " ", raw.strip(" ,.;:\n\t")).strip()
    tokens = name.split()
    # Remove leading prefixes repeatedly (case-insensitive, strip punctuation)
    while tokens and tokens[0].lower().strip(".,/") in _PERSON_PREFIX_STOPWORDS:
        tokens.pop(0)
    # Strip trailing artefacts: isolated s, o, s/o fragments left after alias split
    while tokens and tokens[-1].lower().strip(".,/") in {"s", "o", "s/o", "so"}:
        tokens.pop()
    # Keep at most 3 tokens (most Indian names are 1-3)
    if len(tokens) > 3:
        tokens = tokens[-3:]
    # Remove any token that is a known verb/non-name if it is not capitalised properly
    # Keep only tokens that look like proper names (capitalized)
    # But allow already cleaned names to stay; filter later via _is_plausible_person
    cleaned = " ".join(tokens).strip()
    if cleaned and len(cleaned.split()) > 4:
        cleaned = " ".join(cleaned.split()[:3])
    return cleaned


def _is_plausible_person(name: str) -> bool:
    if not name or len(name) < 2 or len(name) > 60:
        return False
    low = name.strip().lower()
    if low in _PERSON_NOISE_EXACT:
        return False
    if VEHICLE_RE.fullmatch(name.strip().upper()):
        return False
    if FIR_RE.fullmatch(name.strip().upper()):
        return False
    toks = set(low.split())
    if toks & _LOCATION_HINTS and len(toks) <= 3 and "station" in toks:
        return False
    if not re.search(r"[A-Za-z]{2,}", name):
        return False
    if len(name.split()) == 1 and len(name) <= 2:
        return False
    # Reject single-token pronouns / generic words
    if len(name.split()) == 1 and low in _PERSON_NOISE_EXACT:
        return False
    # Reject names containing verbs / non-name tokens
    name_tokens = name.split()
    for tok in name_tokens:
        if tok.lower() in _NON_NAME_VERBS:
            return False
        if tok.lower() in _PERSON_NOISE_EXACT:
            return False
        if not tok[0].isupper():
            return False
        if not re.fullmatch(r"[A-Za-z]+", tok):
            return False
    # Reject names that are all lowercase except first letter? already handled
    return True


def _extract_ps_locations(text: str) -> List[str]:
    """Find location names that immediately follow 'PS' to exclude them from suspects."""
    locs: List[str] = []
    for m in re.finditer(r"\bPS\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", text):
        loc = m.group(1).strip()
        if loc:
            locs.append(loc)
            # Also add single token version
            for tok in loc.split():
                locs.append(tok)
    return [l.lower() for l in locs]


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

def extract_entities_from_text(text: str) -> Dict[str, Any]:
    """
    Extract structured entities from free-form law-enforcement narrative text.

    Args:
        text: FIR narrative / witness statement text.

    Returns:
        Dict with keys:
            suspects: List[str]  – PERSON entities via spaCy
            aliases: List[Dict[str,str]] – [{"primary": ..., "alias": ...}]
            phones: List[str] – normalized 10-digit strings (valid Indian mobiles)
            vehicles: List[str]
            accounts: List[str] – 9-18 digit strings excluding phones
            fir_ids: List[str]
            so_relations: List[Dict[str,str]] – s/o father relations (bonus)
    """
    if not isinstance(text, str):
        text = _safe_str(text, "")

    original = text
    # Normalize vehicles to uppercase for plate matching
    # but keep original for spaCy.
    suspects: List[str] = []
    aliases: List[Dict[str, str]] = []
    so_relations: List[Dict[str, str]] = []

    # --- PERSON via spaCy ---
    nlp = _get_nlp()
    if nlp is not None:
        try:
            doc = nlp(original)  # type: ignore
            for ent in doc.ents:  # type: ignore
                if ent.label_ == "PERSON":
                    name = ent.text.strip()
                    name = re.sub(r"\s+", " ", name).strip(" ,.;")
                    # Handle combined alias entity like "Ramesh Kumar alias Rama"
                    # Split on alias/@ inside entity
                    if re.search(r"\b(alias|aka|@)\b", name, re.IGNORECASE):
                        parts = re.split(r"\s+(?:alias|aka|@)\s+", name, flags=re.IGNORECASE)
                        for part in parts:
                            cleaned = _clean_person_name(part)
                            if _is_plausible_person(cleaned):
                                suspects.append(cleaned)
                        continue
                    # Handle s/o inside entity
                    if re.search(r"\bs/o\b", name, re.IGNORECASE):
                        parts = re.split(r"\s+s/o\s+", name, flags=re.IGNORECASE)
                        for part in parts:
                            cleaned = _clean_person_name(part)
                            if _is_plausible_person(cleaned):
                                # Only first part is suspect; second is father (handled via SO_RE below)
                                # But we add father as s/o relation later; add child for now
                                pass
                        # For s/o, keep only child part as suspect
                        primary_part = re.split(r"\s+s/o\s+", name, flags=re.IGNORECASE)[0]
                        name = primary_part
                    cleaned = _clean_person_name(name)
                    if _is_plausible_person(cleaned):
                        suspects.append(cleaned)
        except Exception as e:
            logger.warning("spaCy NER failed: %s – falling back to regex", e)

    # PS locations to exclude
    ps_locs_lower = set(_extract_ps_locations(original))

    # Fallback if spaCy produced nothing or produced only vehicle/date noise
    # If spaCy produced zero plausible suspects, fall back to regex
    # Also if plausible suspects list is empty after cleaning, use fallback
    suspects = _dedup_preserve_order(suspects)
    # Filter already collected suspects against PS locations and plausibility
    # Remove vehicle/date noise already handled via _is_plausible_person, but double-check
    suspects = [s for s in suspects if s.lower() not in ps_locs_lower and _is_plausible_person(s)]

    if not suspects:
        if nlp is None or _FALLBACK_PERSON_RE:
            candidates = _FALLBACK_PERSON_RE.findall(original)
            filtered = []
            for c in candidates:
                c_clean = _clean_person_name(c)
                if not _is_plausible_person(c_clean):
                    continue
                if c_clean.lower() in ps_locs_lower:
                    continue
                filtered.append(c_clean)
            if re.search(r"(suspect|accused|alias|@|s/o|fir)", original, re.IGNORECASE):
                suspects.extend(filtered[:20])

    suspects = _dedup_preserve_order(suspects)
    # Final fallback filter PS locs
    suspects = [s for s in suspects if s.lower() not in ps_locs_lower]

    # --- Alias variations – strict name pattern, already cleaned via regex but re-clean for safety ---
    for m in ALIAS_RE.finditer(original):
        primary_raw = m.group("primary")
        alias_raw = m.group("alias")
        primary = _clean_person_name(primary_raw)
        alias = _clean_person_name(alias_raw)
        if not _is_plausible_person(primary) or not _is_plausible_person(alias):
            continue
        if primary.lower() == alias.lower():
            continue
        if primary.lower() in ps_locs_lower or alias.lower() in ps_locs_lower:
            continue
        aliases.append({"primary": primary.strip(), "alias": alias.strip()})

    seen_alias_pairs = {(a["primary"].lower(), a["alias"].lower()) for a in aliases}
    for m in ALIAS_INLINE_RE.finditer(original):
        # Skip if already captured by first pattern (same span)
        # Check duplicate pair early
        primary_raw = m.group("primary")
        alias_raw = m.group("alias")
        primary = _clean_person_name(primary_raw)
        alias = _clean_person_name(alias_raw)
        if not _is_plausible_person(primary) or not _is_plausible_person(alias):
            continue
        if primary.lower() in ps_locs_lower or alias.lower() in ps_locs_lower:
            continue
        key = (primary.lower(), alias.lower())
        if key not in seen_alias_pairs:
            aliases.append({"primary": primary.strip(), "alias": alias.strip()})
            seen_alias_pairs.add(key)

    # s/o relations – use strict pattern to avoid capturing alias residue
    for m in SO_RE_STRICT.finditer(original):
        child_raw = re.sub(r"\s+", " ", m.group(1).strip())
        father_raw = re.sub(r"\s+", " ", m.group(2).strip())
        child = _clean_person_name(child_raw)
        father = _clean_person_name(father_raw)
        if not _is_plausible_person(child) or not _is_plausible_person(father):
            continue
        if child.lower() in ps_locs_lower or father.lower() in ps_locs_lower:
            continue
        so_relations.append({"child": child, "father": father})
        if child not in suspects and _is_plausible_person(child):
            # Avoid duplicates already via alias
            if child.lower() not in ps_locs_lower:
                suspects.append(child)
    # Also handle SO_RE fallback for lower alias cases (legacy pattern) if strict found nothing
    if not so_relations:
        for m in SO_RE.finditer(original):
            child_raw = re.sub(r"\s+", " ", m.group(1).strip())
            father_raw = re.sub(r"\s+", " ", m.group(2).strip())
            child = _clean_person_name(child_raw)
            father = _clean_person_name(father_raw)
            if not _is_plausible_person(child) or not _is_plausible_person(father):
                continue
            if child.lower() in ps_locs_lower or father.lower() in ps_locs_lower:
                continue
            # Avoid duplicate of strict
            if {"child": child, "father": father} not in so_relations:
                so_relations.append({"child": child, "father": father})
                if child not in suspects:
                    suspects.append(child)

    # Post-process aliases: if alias primary is a father name, likely alias actually belongs to the child accused
    # e.g., "Sunil Kumar s/o Rajesh Kumar alias Sonu" – Sonu is alias of Sunil, not Rajesh
    if so_relations and aliases:
        father_to_child = {r["father"].lower(): r["child"] for r in so_relations}
        corrected_aliases: List[Dict[str, str]] = []
        for al in aliases:
            p_low = al["primary"].lower()
            if p_low in father_to_child:
                # Reassign to child if child is plausible
                child_name = father_to_child[p_low]
                if _is_plausible_person(child_name):
                    corrected_aliases.append({"primary": child_name, "alias": al["alias"]})
                    continue
            corrected_aliases.append(al)
        aliases = corrected_aliases

    # Final suspect cleanup: re-clean, plausibility, PS exclusion, and ensure alias primaries are included correctly
    father_names_lower = {r["father"].lower() for r in so_relations if _is_plausible_person(r["father"])}
    cleaned_suspects: List[str] = []
    for s in suspects:
        c = _clean_person_name(s)
        if not _is_plausible_person(c) or c.lower() in ps_locs_lower:
            continue
        if c.lower() in father_names_lower:
            is_alias_related = any(al["primary"].lower() == c.lower() or al["alias"].lower() == c.lower() for al in aliases)
            is_child = any(r["child"].lower() == c.lower() for r in so_relations)
            if not is_alias_related and not is_child:
                continue
        cleaned_suspects.append(c)
    # Also ensure every alias primary is represented as suspect (canonical)
    for al in aliases:
        p = al["primary"]
        if p and _is_plausible_person(p) and p not in cleaned_suspects and p.lower() not in ps_locs_lower:
            # Don't add fathers again
            if p.lower() not in father_names_lower or any(r["child"].lower() == p.lower() for r in so_relations):
                cleaned_suspects.append(p)
    suspects = _dedup_preserve_order(cleaned_suspects)

    # --- Phones ---
    raw_phones = PHONE_RE.findall(original)
    # PHONE_RE may return tuples if groups present – flatten
    phones_flat: List[str] = []
    for p in raw_phones:
        if isinstance(p, tuple):
            # Take first non-empty element
            p = next((x for x in p if x), "")
        p = _safe_str(p)
        if not p:
            continue
        norm = _normalize_phone(p)
        if _is_valid_phone(norm):
            phones_flat.append(norm)
        else:
            # Also try to extract 10-digit substring from longer match
            digits = re.sub(r"\D", "", p)
            # Find any 10-digit Indian mobile inside
            for sub in re.findall(r"[6-9]\d{9}", digits):
                phones_flat.append(sub)
    phones = _dedup_preserve_order(phones_flat)

    # --- Vehicles ---
    # Uppercase text for vehicle matching
    vehicles = VEHICLE_RE.findall(original.upper())
    vehicles = _dedup_preserve_order([v.strip() for v in vehicles])

    # --- FIR IDs ---
    fir_ids = FIR_RE.findall(original.upper())
    fir_ids = _dedup_preserve_order([f.strip() for f in fir_ids])

    # --- Bank accounts (9-18 digits) excluding phones & vehicle numeric parts ---
    candidates = BANK_RE.findall(original)
    # Filter: exclude those that are valid phones (already captured) and those part of FIR/timestamp
    phone_set = set(phones)
    # Also exclude FIR numeric fragments?
    # Keep candidate only if not in phone_set and not a sub-string of vehicle
    vehicle_digits_set = set(re.sub(r"\D", "", v) for v in vehicles)
    accounts: List[str] = []
    for cand in candidates:
        cand = _safe_str(cand)
        if not cand or not cand.isdigit():
            continue
        # Exclude leading zeros heavy? But keep as is
        if cand in phone_set:
            continue
        # Phone digits are 10; accounts can also be 10 – need to disambiguate:
        # If candidate length ==10 and is valid phone and appears near phone context (mobile, phone, msisdn) – we already filtered.
        # But candidate exactly 10 digits that equals a phone should be excluded; otherwise keep if flagged as account near keywords "account", "acc", "bank"
        # To reduce false positives, exclude pure 10-digit numbers unless context suggests account.
        # However spec says simple \b\d{9,18}\b – so we keep all, but exclude phones already.
        # Also exclude small vehicle fragments
        if cand in vehicle_digits_set:
            continue
        # Exclude years 1900-2100-ish single candidates that look like dates?
        # Keep only 9-18 length and not obviously a phone duplicate
        if 9 <= len(cand) <= 18:
            # Additional heuristic: if original text has "account" near candidate position – boost confidence but not required
            accounts.append(cand)
    accounts = _dedup_preserve_order(accounts)
    # Remove accounts that are actually fir year fragments + etc – but FIR already has letters, so safe.

    # Deduplicate phones that accidentally also appear as accounts
    accounts = [a for a in accounts if a not in phone_set]

    return {
        "suspects": suspects,
        "aliases": aliases,
        "so_relations": so_relations,
        "phones": phones,
        "vehicles": vehicles,
        "accounts": accounts,
        "fir_ids": fir_ids,
    }


# ---------------------------------------------------------------------------
# Parsers – FIR JSON
# ---------------------------------------------------------------------------

def _read_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Robustly read fir_samples.json – handles array, object with key, or JSONL."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"FIR JSON not found: {file_path}")
    # Use utf-8-sig to strip BOM if present (Windows PowerShell Set-Content adds BOM)
    try:
        text = p.read_text(encoding="utf-8-sig", errors="ignore").strip()
    except Exception:
        text = p.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try JSONL fallback
        data = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except Exception:
                continue
        if data:
            return data if isinstance(data, list) else [data]
        raise

    if isinstance(data, dict):
        # Common wrappers: {"firs": [...]} or {"data": [...]}
        for key in ("firs", "data", "records", "items", "fir_samples"):
            if key in data and isinstance(data[key], list):
                return data[key]
        # Single record dict
        return [data]
    if isinstance(data, list):
        return data
    return []


def parse_fir_json(file_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses fir_samples.json (fields: fir_no, ps_name, date, text) into preliminary nodes/edges.

    Returns:
        (nodes, edges) – CrimeCase + Suspect/Phone/Account nodes, OPERATES & CO_ACCUSED_IN edges.
    """
    logger.info("Parsing FIR JSON: %s", file_path)
    try:
        records = _read_json_file(file_path)
    except FileNotFoundError:
        logger.warning("FIR file not found – returning empty graph: %s", file_path)
        return [], []
    except Exception as e:
        logger.error("Failed to parse FIR JSON %s: %s", file_path, e)
        return [], []

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen_node_ids: set = set()
    alias_map_accum: Dict[str, str] = {}

    def _add_node(node: Dict[str, Any]):
        nid = node["id"]
        if nid not in seen_node_ids:
            seen_node_ids.add(nid)
            nodes.append(node)
        else:
            # Merge metadata if duplicate (e.g., same CrimeCase appearing twice)
            for existing in nodes:
                if existing["id"] == nid:
                    # Merge evidence sources
                    existing_meta = existing.get("metadata", {})
                    new_meta = node.get("metadata", {})
                    # Combine aliases if present
                    if "aliases" in new_meta:
                        existing_meta.setdefault("aliases", [])
                        for a in new_meta["aliases"]:
                            if a not in existing_meta["aliases"]:
                                existing_meta["aliases"].append(a)
                    break

    for idx, entry in enumerate(records):
        if not isinstance(entry, dict):
            logger.warning("Skipping non-dict FIR record at index %d: %r", idx, entry)
            continue

        fir_no = _safe_str(entry.get("fir_no") or entry.get("firNo") or entry.get("FIR_no") or entry.get("FIR") or entry.get("case_no") or entry.get("id") or f"FIR-UNKNOWN-{idx}")
        # Normalize FIR ID uppercase & hyphen
        fir_no_norm = fir_no.strip().upper()
        if not FIR_RE.search(fir_no_norm):
            # Try to construct from components if FIR field looks like "CR0142"
            base = re.sub(r"\s+", "", fir_no_norm)
            if re.match(r"^[A-Z0-9]+$", base) and base[:3] != "FIR":
                # Leave as-is but sanitize
                pass

        ps_name = _safe_str(entry.get("ps_name") or entry.get("psName") or entry.get("police_station") or entry.get("station") or "Unknown PS")
        date_raw = _safe_str(entry.get("date") or entry.get("timestamp") or entry.get("fir_date") or entry.get("incident_date") or "")
        timestamp_iso = _normalize_timestamp(date_raw) if date_raw else datetime.now(timezone.utc).isoformat()
        text = _safe_str(entry.get("text") or entry.get("narrative") or entry.get("description") or entry.get("content") or "")

        # CrimeCase node
        crime_id = f"crime_{_sanitize_id(fir_no_norm)}"
        crime_node: Dict[str, Any] = {
            "id": crime_id,
            "type": "CrimeCase",
            "label": fir_no_norm,
            "metadata": {
                "ps_name": ps_name,
                "date": timestamp_iso,
                "text_snippet": text[:500],
                "evidence_source": fir_no_norm,
            },
        }
        _add_node(crime_node)

        # Extract entities from FIR text
        extracted = extract_entities_from_text(text)
        # Also consider FIR ID itself if not in text
        if fir_no_norm not in extracted.get("fir_ids", []):
            extracted["fir_ids"].append(fir_no_norm)

        # Alias map accumulation for later dedup – alias (lower) -> primary (original casing)
        for alias_entry in extracted.get("aliases", []):
            primary = _safe_str(alias_entry.get("primary", ""))
            alias = _safe_str(alias_entry.get("alias", ""))
            if primary and alias:
                # Normalize key lower
                # Map alias -> primary (spec: linking Rakesh alias Bunty)
                alias_map_accum[alias.lower()] = primary
                alias_map_accum[primary.lower()] = primary  # ensure primary maps to itself
                # Also create suspect nodes for both if not already via PERSON list
                if primary not in extracted["suspects"]:
                    extracted["suspects"].append(primary)
                if alias not in extracted["suspects"]:
                    # Still add alias as suspect variant; resolver will merge
                    extracted["suspects"].append(alias)

        suspects_in_fir: List[str] = []
        for suspect_name in extracted.get("suspects", []):
            suspect_name = _safe_str(suspect_name)
            if not suspect_name or len(suspect_name) < 2:
                continue
            # Filter obvious non-person noise leftover
            if suspect_name.lower() in {"fir", "police station", "district", "unknown"}:
                continue
            suspects_in_fir.append(suspect_name)
            suspect_id = f"suspect_{_sanitize_id(suspect_name.lower())}"
            # Collect aliases for this suspect from extracted aliases where primary matches
            aliases_for_this = [
                a["alias"] for a in extracted.get("aliases", []) if a["primary"].strip().lower() == suspect_name.lower()
            ]
            suspect_node: Dict[str, Any] = {
                "id": suspect_id,
                "type": "Suspect",
                "label": suspect_name,
                "metadata": {
                    "aliases": aliases_for_this,
                    "ps_name": ps_name,
                    "fir_no": fir_no_norm,
                    "evidence_source": fir_no_norm,
                    "so_relations": [r for r in extracted.get("so_relations", []) if r["child"].lower() == suspect_name.lower()],
                },
            }
            _add_node(suspect_node)

        # Deduplicate suspects_in_fir preserve order
        suspects_in_fir = _dedup_preserve_order(suspects_in_fir)

        # Edges: Suspect OPERATES CrimeCase  and  Suspect USES Phone/Account if present
        for suspect_name in suspects_in_fir:
            suspect_id = f"suspect_{_sanitize_id(suspect_name.lower())}"
            edges.append(
                {
                    "source": suspect_id,
                    "target": crime_id,
                    "type": "OPERATES",
                    "metadata": {
                        "timestamp": timestamp_iso,
                        "evidence_source": fir_no_norm,
                    },
                }
            )

        # CO_ACCUSED_IN edges: complete graph among suspects in same FIR
        for i in range(len(suspects_in_fir)):
            for j in range(i + 1, len(suspects_in_fir)):
                s1 = f"suspect_{_sanitize_id(suspects_in_fir[i].lower())}"
                s2 = f"suspect_{_sanitize_id(suspects_in_fir[j].lower())}"
                # Undirected concept: create one edge s1->s2; companion checker may count reverse as same, but we create single directed for schema
                edges.append(
                    {
                        "source": s1,
                        "target": s2,
                        "type": "CO_ACCUSED_IN",
                        "metadata": {
                            "timestamp": timestamp_iso,
                            "evidence_source": fir_no_norm,
                            "fir_no": fir_no_norm,
                        },
                    }
                )

        # Phone nodes from FIR text (if any) + USES edges
        for phone in extracted.get("phones", []):
            phone_id = f"phone_{_sanitize_id(phone)}"
            phone_node = {
                "id": phone_id,
                "type": "Phone",
                "label": phone,
                "metadata": {"evidence_source": fir_no_norm, "fir_no": fir_no_norm},
            }
            _add_node(phone_node)
            # Link first suspect to phone via USES if suspects exist; else CrimeCase USES? Use Suspect USES
            if suspects_in_fir:
                # Link each suspect? Link primary only to avoid edge explosion – link all for completeness but capped
                for s_name in suspects_in_fir[:3]:  # link up to 3 primary suspects
                    s_id = f"suspect_{_sanitize_id(s_name.lower())}"
                    edges.append(
                        {
                            "source": s_id,
                            "target": phone_id,
                            "type": "USES",
                            "metadata": {
                                "timestamp": timestamp_iso,
                                "evidence_source": fir_no_norm,
                            },
                        }
                    )

        # Account nodes from FIR text
        for acc in extracted.get("accounts", []):
            acc_id = f"account_{_sanitize_id(acc)}"
            acc_node = {
                "id": acc_id,
                "type": "Account",
                "label": acc,
                "metadata": {"evidence_source": fir_no_norm, "fir_no": fir_no_norm},
            }
            _add_node(acc_node)
            if suspects_in_fir:
                for s_name in suspects_in_fir[:3]:
                    s_id = f"suspect_{_sanitize_id(s_name.lower())}"
                    edges.append(
                        {
                            "source": s_id,
                            "target": acc_id,
                            "type": "OPERATES",
                            "metadata": {
                                "timestamp": timestamp_iso,
                                "evidence_source": fir_no_norm,
                                "relation": "operates_account",
                            },
                        }
                    )

        # Vehicle nodes – treat as metadata on suspect or standalone? Create as Location/vehicle-like; but type set allows only enumerated types per schema.
        # Spec nodes types: Suspect | Phone | Account | Location | CrimeCase
        # Vehicle numbers do not fit directly; we store them as metadata on Suspect or as Phone-like but we will store as Location with subtype.
        # Instead create a Phone-like placeholder but better to skip standalone vehicle nodes to stay schema-compliant and store as metadata.
        # We'll store vehicle numbers as Suspect metadata vehicles
        if extracted.get("vehicles"):
            for s_name in suspects_in_fir[:1]:
                s_id = f"suspect_{_sanitize_id(s_name.lower())}"
                for node in nodes:
                    if node["id"] == s_id:
                        node["metadata"].setdefault("vehicles", [])
                        for v in extracted["vehicles"]:
                            if v not in node["metadata"]["vehicles"]:
                                node["metadata"]["vehicles"].append(v)

    logger.info("FIR parse complete: %d nodes, %d edges, %d alias mappings", len(nodes), len(edges), len(alias_map_accum))
    # Store alias accumulation on nodes metadata for orchestrator retrieval via closure? We return alias_map separately via global? Instead orchestrator recomputes aliases.
    # Attach to function result via side-car file? Simply return nodes/edges; orchestrator will re-extract alias map from text if needed.
    # But we need to expose alias map: we store it as attribute on function for caller to retrieve if needed.
    parse_fir_json._last_alias_map = alias_map_accum  # type: ignore
    return nodes, edges


# ---------------------------------------------------------------------------
# Parsers – CDR CSV
# ---------------------------------------------------------------------------

def _iter_csv_rows(file_path: str) -> List[Dict[str, Any]]:
    """
    Gracefully iterate CSV rows handling missing/NaN, via pandas if available else csv module.
    Returns list of dicts with stripped keys/values.
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"CSV not found: {file_path}")

    rows: List[Dict[str, Any]] = []

    # Try pandas first for robust NA handling
    if _PANDAS_AVAILABLE:
        try:
            # dtype=str to preserve leading zeros for phones/accounts
            df = pd.read_csv(file_path, dtype=str, keep_default_na=True, na_values=["", "NA", "N/A", "NULL", "null", "nan", "NaN"])  # type: ignore
            # Normalize columns lower+strip
            df.columns = [str(c).strip().lower() for c in df.columns]  # type: ignore
            # Replace NaN with empty string for safe iteration
            df = df.fillna("")  # type: ignore
            for _, r in df.iterrows():  # type: ignore
                # Convert Series to dict with lower keys
                row = {str(k).strip().lower(): _safe_str(v) for k, v in r.items()}  # type: ignore
                rows.append(row)
            logger.info("CDR/Bank CSV read via pandas: %d rows from %s", len(rows), file_path)
            return rows
        except Exception as e:
            logger.warning("Pandas CSV read failed (%s) – falling back to csv module: %s", file_path, e)

    # Fallback: csv module
    try:
        with p.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            # Detect dialect
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
            except Exception:
                dialect = csv.excel
            reader = csv.DictReader(f, dialect=dialect)
            # Normalize fieldnames
            if reader.fieldnames:
                reader.fieldnames = [str(fn).strip().lower() for fn in reader.fieldnames]
            for raw_row in reader:
                # Skip empty rows
                if not raw_row:
                    continue
                normalized = {}
                for k, v in raw_row.items():
                    key = str(k).strip().lower() if k else ""
                    normalized[key] = _safe_str(v)
                # Skip rows where all values empty
                if all(not v for v in normalized.values()):
                    continue
                rows.append(normalized)
        logger.info("CSV read via csv module: %d rows from %s", len(rows), file_path)
    except Exception as e:
        logger.error("CSV fallback read failed %s: %s", file_path, e)
        return []
    return rows


def parse_cdr_csv(file_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses cdr_tower_dump.csv (columns: caller_msisdn, receiver_msisdn, timestamp, duration_sec, imei, tower_id)
    into Phone/Location nodes and CALLED edges.

    Gracefully skips rows with missing/NaN critical fields.
    """
    logger.info("Parsing CDR CSV: %s", file_path)
    try:
        rows = _iter_csv_rows(file_path)
    except FileNotFoundError:
        logger.warning("CDR file not found – returning empty: %s", file_path)
        return [], []
    except Exception as e:
        logger.error("Failed to iterate CDR CSV %s: %s", file_path, e)
        return [], []

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen_node_ids: set = set()

    def _add_node(node: Dict[str, Any]):
        nid = node["id"]
        if nid not in seen_node_ids:
            seen_node_ids.add(nid)
            nodes.append(node)
        else:
            # Merge metadata if location appears multiple times
            pass

    for idx, row in enumerate(rows):
        caller_raw = row.get("caller_msisdn") or row.get("caller") or row.get("from") or row.get("source") or ""
        receiver_raw = row.get("receiver_msisdn") or row.get("receiver") or row.get("callee") or row.get("to") or row.get("target") or ""
        timestamp_raw = row.get("timestamp") or row.get("call_time") or row.get("date") or row.get("datetime") or ""
        duration_raw = row.get("duration_sec") or row.get("duration") or row.get("call_duration") or "0"
        imei_raw = row.get("imei") or row.get("imei_no") or ""
        tower_raw = row.get("tower_id") or row.get("tower") or row.get("cell_id") or row.get("location") or ""

        caller_raw = _safe_str(caller_raw)
        receiver_raw = _safe_str(receiver_raw)
        if not caller_raw or not receiver_raw:
            logger.debug("Skipping CDR row %d missing caller/receiver: %r", idx, row)
            continue

        caller_norm = _normalize_phone(caller_raw)
        receiver_norm = _normalize_phone(receiver_raw)
        # Validate at least receiver/caller look like phones; if not valid, keep raw digits as fallback
        if not _is_valid_phone(caller_norm):
            # Try to extract valid phone substring from raw
            sub = re.findall(r"[6-9]\d{9}", re.sub(r"\D", "", caller_raw))
            if sub:
                caller_norm = sub[0]
            else:
                logger.debug("Skipping invalid caller phone %r row %d", caller_raw, idx)
                continue
        if not _is_valid_phone(receiver_norm):
            sub = re.findall(r"[6-9]\d{9}", re.sub(r"\D", "", receiver_raw))
            if sub:
                receiver_norm = sub[0]
            else:
                logger.debug("Skipping invalid receiver phone %r row %d", receiver_raw, idx)
                continue

        timestamp_iso = _normalize_timestamp(timestamp_raw) if timestamp_raw else datetime.now(timezone.utc).isoformat()

        try:
            duration_val = int(float(_safe_str(duration_raw, "0") or 0))
        except Exception:
            duration_val = 0
        if duration_val < 0:
            duration_val = 0

        imei_val = _safe_str(imei_raw)
        tower_val = _safe_str(tower_raw)

        caller_id = f"phone_{_sanitize_id(caller_norm)}"
        receiver_id = f"phone_{_sanitize_id(receiver_norm)}"

        # Phone nodes
        for pid, pnum, imei in [(caller_id, caller_norm, imei_val), (receiver_id, receiver_norm, "")]:
            # Only caller has IMEI context; receiver IMEI not known from this row
            existing = next((n for n in nodes if n["id"] == pid), None)
            if existing is None:
                meta: Dict[str, Any] = {"evidence_source": "CDR Log"}
                if imei:
                    meta["imei"] = imei
                # Collect tower associations as list
                if tower_val and pid == caller_id:
                    meta["tower_ids"] = [tower_val]
                _add_node(
                    {
                        "id": pid,
                        "type": "Phone",
                        "label": pnum,
                        "metadata": meta,
                    }
                )
            else:
                # Update tower list if new
                if tower_val and pid == caller_id:
                    existing["metadata"].setdefault("tower_ids", [])
                    if tower_val not in existing["metadata"]["tower_ids"]:
                        existing["metadata"]["tower_ids"].append(tower_val)

        # Location node for tower
        if tower_val:
            tower_id = f"location_{_sanitize_id(tower_val)}"
            if tower_id not in seen_node_ids:
                _add_node(
                    {
                        "id": tower_id,
                        "type": "Location",
                        "label": tower_val,
                        "metadata": {"tower_id": tower_val, "evidence_source": "CDR Log"},
                    }
                )

        # CALLED edge
        edge_meta: Dict[str, Any] = {
            "timestamp": timestamp_iso,
            "duration": duration_val,
            "evidence_source": "CDR Log",
        }
        if imei_val:
            edge_meta["imei"] = imei_val
        if tower_val:
            edge_meta["tower_id"] = tower_val

        edges.append(
            {
                "source": caller_id,
                "target": receiver_id,
                "type": "CALLED",
                "metadata": edge_meta,
            }
        )

    logger.info("CDR parse complete: %d nodes (%d phones, %d locations), %d edges", len(nodes), sum(1 for n in nodes if n["type"] == "Phone"), sum(1 for n in nodes if n["type"] == "Location"), len(edges))
    return nodes, edges


# ---------------------------------------------------------------------------
# Parsers – Bank CSV
# ---------------------------------------------------------------------------

def parse_bank_csv(file_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses bank_transactions.csv (columns: sender_acc, receiver_acc, amount, timestamp, tx_id)
    into Account nodes and TRANSFERRED edges.
    """
    logger.info("Parsing Bank CSV: %s", file_path)
    try:
        rows = _iter_csv_rows(file_path)
    except FileNotFoundError:
        logger.warning("Bank file not found – returning empty: %s", file_path)
        return [], []
    except Exception as e:
        logger.error("Failed to iterate Bank CSV %s: %s", file_path, e)
        return [], []

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen_node_ids: set = set()

    def _add_account_node(acc_raw: str):
        acc = _safe_str(acc_raw)
        if not acc:
            return None
        # Keep only digits for account; but allow alphanumeric? Spec: 9-18 digits. Strict digits.
        digits = re.sub(r"\D", "", acc)
        # If original had non-digits but length ok, keep original stripped?
        # Prefer digits if candidate matches bank regex
        if BANK_RE.fullmatch(digits) or (9 <= len(digits) <= 18 and digits.isdigit()):
            acc_label = digits
        else:
            # Fallback: keep raw alphanumeric if it looks like account
            if 9 <= len(acc) <= 18:
                acc_label = acc
            else:
                return None
        acc_id = f"account_{_sanitize_id(acc_label)}"
        if acc_id not in seen_node_ids:
            seen_node_ids.add(acc_id)
            nodes.append(
                {
                    "id": acc_id,
                    "type": "Account",
                    "label": acc_label,
                    "metadata": {"evidence_source": "Bank Txn"},
                }
            )
        return acc_id

    for idx, row in enumerate(rows):
        sender_raw = row.get("sender_acc") or row.get("sender") or row.get("from_acc") or row.get("from") or row.get("source_acc") or ""
        receiver_raw = row.get("receiver_acc") or row.get("receiver") or row.get("to_acc") or row.get("to") or row.get("target_acc") or ""
        amount_raw = row.get("amount") or row.get("amt") or row.get("value") or "0"
        timestamp_raw = row.get("timestamp") or row.get("date") or row.get("txn_date") or row.get("time") or ""
        tx_id_raw = row.get("tx_id") or row.get("txn_id") or row.get("transaction_id") or row.get("id") or ""

        sender_raw = _safe_str(sender_raw)
        receiver_raw = _safe_str(receiver_raw)
        if not sender_raw or not receiver_raw:
            logger.debug("Skipping bank row %d missing sender/receiver: %r", idx, row)
            continue

        # Filter sender/receiver that look like NaN
        if sender_raw.lower() in {"nan", "none"} or receiver_raw.lower() in {"nan", "none"}:
            continue

        sender_id = _add_account_node(sender_raw)
        receiver_id = _add_account_node(receiver_raw)
        if not sender_id or not receiver_id:
            logger.debug("Skipping bank row %d invalid accounts: %r / %r", idx, sender_raw, receiver_raw)
            continue
        if sender_id == receiver_id:
            logger.debug("Skipping self-transfer row %d %s", idx, sender_id)
            continue

        timestamp_iso = _normalize_timestamp(timestamp_raw) if timestamp_raw else datetime.now(timezone.utc).isoformat()
        tx_id = _safe_str(tx_id_raw, f"txn_{idx}")

        try:
            amount_val = float(_safe_str(amount_raw, "0").replace(",", ""))
        except Exception:
            amount_val = 0.0
        if amount_val < 0:
            amount_val = abs(amount_val)

        edges.append(
            {
                "source": sender_id,
                "target": receiver_id,
                "type": "TRANSFERRED",
                "metadata": {
                    "timestamp": timestamp_iso,
                    "amount": amount_val,
                    "tx_id": tx_id,
                    "evidence_source": "Bank Txn",
                },
            }
        )

    logger.info("Bank parse complete: %d account nodes, %d edges", len(nodes), len(edges))
    return nodes, edges


# ---------------------------------------------------------------------------
# Unified orchestrator
# ---------------------------------------------------------------------------

def _deduplicate_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate by node id preserving first occurrence, merging metadata lists."""
    seen: Dict[str, Dict[str, Any]] = {}
    for n in nodes:
        nid = n.get("id")
        if not nid:
            continue
        if nid not in seen:
            seen[nid] = n
        else:
            # Merge metadata evidence sources
            existing_meta = seen[nid].setdefault("metadata", {})
            new_meta = n.get("metadata", {})
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
    return list(seen.values())


def _deduplicate_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate edges by (source, target, type, timestamp, amount) signature."""
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        typ = e.get("type")
        meta = e.get("metadata", {})
        # Signature includes timestamp & amount/tx_id to keep distinct transactions separate
        sig = (
            src,
            tgt,
            typ,
            meta.get("timestamp"),
            meta.get("amount"),
            meta.get("tx_id"),
            meta.get("duration"),
            meta.get("evidence_source"),
        )
        if sig not in seen:
            seen.add(sig)
            out.append(e)
    return out


def parse_all_sources(data_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Master orchestrator – reads all three sources from data_dir and returns clean graph.

    Reads:
        {data_dir}/fir_samples.json
        {data_dir}/cdr_tower_dump.csv
        {data_dir}/bank_transactions.csv

    Returns:
        {
          "nodes": [{"id": str, "type": "Suspect"|"Phone"|"Account"|"Location"|"CrimeCase", "label": str, "metadata": {...}}, ...],
          "edges": [{"source": str, "target": str, "type": "CALLED"|"TRANSFERRED"|"OPERATES"|"USES"|"CO_ACCUSED_IN", "metadata": {"timestamp": ISO_8601_string, ...}}, ...]
        }

    Handles missing files gracefully (logs warning, continues with available sources).
    Uses `resolver.resolve_suspect_aliases` for phonetic/fuzzy deduplication of Suspect nodes.
    """
    data_path = Path(data_dir)
    logger.info("Orchestrator parse_all_sources from: %s", data_path)

    all_nodes: List[Dict[str, Any]] = []
    all_edges: List[Dict[str, Any]] = []
    global_alias_map: Dict[str, str] = {}

    # --- FIR ---
    fir_path = data_path / "fir_samples.json"
    if fir_path.exists():
        try:
            fir_nodes, fir_edges = parse_fir_json(str(fir_path))
            all_nodes.extend(fir_nodes)
            all_edges.extend(fir_edges)
            # Retrieve alias map captured during parse_fir_json
            alias_map = getattr(parse_fir_json, "_last_alias_map", {})  # type: ignore
            if isinstance(alias_map, dict):
                global_alias_map.update(alias_map)
        except Exception as e:
            logger.error("FIR orchestrator failure: %s", e, exc_info=True)
    else:
        logger.warning("FIR file missing at %s – skipping", fir_path)

    # --- CDR ---
    cdr_path = data_path / "cdr_tower_dump.csv"
    if cdr_path.exists():
        try:
            cdr_nodes, cdr_edges = parse_cdr_csv(str(cdr_path))
            all_nodes.extend(cdr_nodes)
            all_edges.extend(cdr_edges)
        except Exception as e:
            logger.error("CDR orchestrator failure: %s", e, exc_info=True)
    else:
        logger.warning("CDR file missing at %s – skipping", cdr_path)

    # --- Bank ---
    bank_path = data_path / "bank_transactions.csv"
    if bank_path.exists():
        try:
            bank_nodes, bank_edges = parse_bank_csv(str(bank_path))
            all_nodes.extend(bank_nodes)
            all_edges.extend(bank_edges)
        except Exception as e:
            logger.error("Bank orchestrator failure: %s", e, exc_info=True)
    else:
        logger.warning("Bank file missing at %s – skipping", bank_path)

    # If no nodes at all, return empty schema early
    if not all_nodes and not all_edges:
        logger.warning("No data found in %s – returning empty graph", data_path)
        return {"nodes": [], "edges": []}

    # Deduplicate nodes before resolver (cheaper)
    all_nodes = _deduplicate_nodes(all_nodes)

    # If still no alias map discovered, try to synthesize from nodes: scan suspect aliases metadata
    # Also include s/o variations as alias hints
    if not global_alias_map:
        for n in all_nodes:
            if n.get("type") == "Suspect":
                meta_aliases = n.get("metadata", {}).get("aliases", [])
                canon = n.get("label", "")
                for a in meta_aliases:
                    if isinstance(a, str) and a:
                        global_alias_map[a.lower()] = canon

    # --- Resolver dedup ---
    # Import resolver lazily to avoid circular import at top-level
    try:
        from .resolver import resolve_suspect_aliases  # type: ignore

        try:
            resolved_nodes = resolve_suspect_aliases(all_nodes, global_alias_map)
        except TypeError:
            # Fallback if resolver has different signature
            resolved_nodes = resolve_suspect_aliases(all_nodes, global_alias_map)  # type: ignore
    except ImportError:
        try:
            from backend.app.core.resolver import resolve_suspect_aliases as _resolve  # type: ignore

            resolved_nodes = _resolve(all_nodes, global_alias_map)  # type: ignore
        except Exception as e:
            logger.warning("Resolver import failed (%s) – skipping dedup", e)
            resolved_nodes = all_nodes
    except Exception as e:
        logger.error("Resolver failed: %s – using raw nodes", e, exc_info=True)
        resolved_nodes = all_nodes

    # Build alias ID remapping for edges
    # Resolver exposes global mapping via attribute or helper; we reconstruct mapping by comparing old vs new suspect IDs
    # Approach: If resolver exposed _ALIAS_ID_MAP, use it; else infer by label matching
    alias_id_map: Dict[str, str] = {}
    try:
        from . import resolver as _resolver_mod  # type: ignore

        if hasattr(_resolver_mod, "get_alias_id_map"):
            alias_id_map = _resolver_mod.get_alias_id_map()  # type: ignore
        elif hasattr(_resolver_mod, "ALIAS_ID_MAP"):
            alias_id_map = dict(getattr(_resolver_mod, "ALIAS_ID_MAP", {}))  # type: ignore
        elif hasattr(_resolver_mod, "_ALIAS_ID_MAP"):
            alias_id_map = dict(getattr(_resolver_mod, "_ALIAS_ID_MAP", {}))  # type: ignore
    except Exception:
        pass

    # Fallback inference: if alias_id_map empty, build map by matching lower labels to canonical IDs in resolved_nodes
    if not alias_id_map:
        # Map lower label -> canonical node id among resolved suspects
        label_to_canonical: Dict[str, str] = {}
        for n in resolved_nodes:
            if n.get("type") == "Suspect":
                label_to_canonical[n.get("label", "").strip().lower()] = n["id"]
                for alias in n.get("metadata", {}).get("aliases", []) or []:
                    if isinstance(alias, str):
                        label_to_canonical[alias.strip().lower()] = n["id"]
        # For each original suspect node, see if its label lower maps to different canonical id
        for orig in all_nodes:
            if orig.get("type") != "Suspect":
                continue
            orig_id = orig["id"]
            orig_label_lower = orig.get("label", "").strip().lower()
            canon_id = label_to_canonical.get(orig_label_lower)
            if canon_id and canon_id != orig_id:
                alias_id_map[orig_id] = canon_id
            # Also map alias-derived ids (alias name sanitized)
            for alias in orig.get("metadata", {}).get("aliases", []) or []:
                if isinstance(alias, str):
                    alias_id = f"suspect_{_sanitize_id(alias.lower())}"
                    canon_for_alias = label_to_canonical.get(alias.lower())
                    if canon_for_alias and alias_id != canon_for_alias:
                        alias_id_map[alias_id] = canon_for_alias

    # Also map alias name lower -> canonical ID via global_alias_map
    if global_alias_map:
        # Build canonical label lower -> id
        canon_lookup = {n["label"].strip().lower(): n["id"] for n in resolved_nodes if n.get("type") == "Suspect"}
        for alias_lower, primary in global_alias_map.items():
            primary_lower = primary.strip().lower() if isinstance(primary, str) else ""
            alias_id = f"suspect_{_sanitize_id(alias_lower)}"
            canon_id = canon_lookup.get(primary_lower) or canon_lookup.get(alias_lower)
            if canon_id and alias_id != canon_id:
                alias_id_map[alias_id] = canon_id
            # Also alias string itself lower mapping
            if alias_lower in canon_lookup and alias_id != canon_lookup[alias_lower]:
                alias_id_map[alias_id] = canon_lookup[alias_lower]

    # Remap edges source/target via alias_id_map (handle transitive closure)
    def _resolve_id(node_id: str) -> str:
        visited = set()
        cur = node_id
        while cur in alias_id_map and cur not in visited:
            visited.add(cur)
            cur = alias_id_map[cur]
        return cur

    remapped_edges: List[Dict[str, Any]] = []
    for e in all_edges:
        src = _resolve_id(_safe_str(e.get("source")))
        tgt = _resolve_id(_safe_str(e.get("target")))
        # Skip self-loops introduced by merging (e.g., co-accused after merge) unless allowed – drop self-loop CO_ACCUSED_IN
        if src == tgt and e.get("type") == "CO_ACCUSED_IN":
            continue
        # Skip edges where remapped node no longer exists (should not happen after resolution)
        new_edge = dict(e)
        new_edge["source"] = src
        new_edge["target"] = tgt
        # Ensure metadata has required fields
        meta = new_edge.setdefault("metadata", {})
        if "timestamp" not in meta or not meta["timestamp"]:
            meta["timestamp"] = datetime.now(timezone.utc).isoformat()
        else:
            meta["timestamp"] = _normalize_timestamp(meta["timestamp"])
        if "evidence_source" not in meta:
            meta["evidence_source"] = "Unknown"
        # Normalize amount/duration if present
        if "amount" in meta:
            try:
                meta["amount"] = float(meta["amount"])
            except Exception:
                meta["amount"] = 0.0
        if "duration" in meta:
            try:
                meta["duration"] = int(meta["duration"])
            except Exception:
                meta["duration"] = 0
        remapped_edges.append(new_edge)

    # Deduplicate edges after remapping
    remapped_edges = _deduplicate_edges(remapped_edges)

    # Final dedup nodes – resolved_nodes already deduped; but ensure any Phone/Account duplicates from CDR/Bank merged
    final_nodes = _deduplicate_nodes(resolved_nodes)

    # Validate schema – ensure types are among allowed; coerce unknown to valid
    allowed_node_types = {"Suspect", "Phone", "Account", "Location", "CrimeCase"}
    allowed_edge_types = {"CALLED", "TRANSFERRED", "OPERATES", "USES", "CO_ACCUSED_IN"}
    for n in final_nodes:
        if n.get("type") not in allowed_node_types:
            logger.warning("Correcting invalid node type %r for %s -> Suspect", n.get("type"), n.get("id"))
            n["type"] = "Suspect"
        if "label" not in n:
            n["label"] = n.get("id", "unknown")
        if "metadata" not in n or not isinstance(n["metadata"], dict):
            n["metadata"] = {}

    for e in remapped_edges:
        if e.get("type") not in allowed_edge_types:
            logger.warning("Correcting invalid edge type %r -> OPERATES", e.get("type"))
            e["type"] = "OPERATES"

    logger.info(
        "Orchestrator complete: %d final nodes, %d final edges (from %d raw nodes, %d raw edges)",
        len(final_nodes),
        len(remapped_edges),
        len(all_nodes),
        len(all_edges),
    )

    return {"nodes": final_nodes, "edges": remapped_edges}


# Expose alias for external importers expecting `parse_all`
__all__ = [
    "extract_entities_from_text",
    "parse_fir_json",
    "parse_cdr_csv",
    "parse_bank_csv",
    "parse_all_sources",
]
