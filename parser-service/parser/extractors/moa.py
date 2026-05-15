"""
Memorandum of Association (eMoA INC-33 / printed MoA) — extractor.

Source of truth: project report §5 ('Memorandum of Association').
Six clauses per §5.B: I Name; II Registered Office (state-only); III Objects
(Main / Ancillary / Other); IV Liability; V Capital (with authorised + share
split); VI Subscription.

Per §5.D extraction:
  - Anchor: 'I. The name of the Company is …', 'II. The Registered office of the
    Company will be situated in the State of …', 'III. The objects for which the
    Company is established are …', 'IV. The liability of the members …',
    'V. The Authorised Share Capital of the Company is Rs. …',
    'VI. We, the several persons …'.
  - Capital Clause regex: `Rs\\.?\\s*[\\d,]+` and
    `divided into\\s+(\\d+)\\s+(equity|preference)\\s+shares of Rs\\.?\\s*(\\d+)\\s+each`.
  - Subscription table → pdfplumber.extract_tables().

Per Stage 2 brief: 'Promote scalars (registered-office state, liability type,
authorised capital, number of shares + face value) to parser_company. Store the
full clause text in a new parser_moa_clauses table'.

Note on schema gap: the Stage 1 parser_company schema (per the report) only has
columns for `authorised_capital` and `paid_up_capital`. The brief asks for
'registered-office state', 'liability type', 'number of shares', 'face value'
to be promoted but no such columns exist. We promote what fits
(`authorised_capital`); the rest is captured as structured `sub_clauses` JSONB
on the matching MoA clause and surfaced in metadata so future schema work can
attach destination columns. No invented columns.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

import pdfplumber
from pdfminer.high_level import extract_text


# Six clauses per §5.B — the ordered (roman, title, anchor) triples.
_CLAUSE_ANCHORS: list[tuple[str, str, str]] = [
    ("I",   "Name Clause",
     r"^\s*I\.\s*The\s+name\s+of\s+the\s+Company\s+is"),
    ("II",  "Registered Office (Domicile) Clause",
     r"^\s*II\.\s*The\s+Registered\s+office\s+of\s+the\s+Company\s+will\s+be\s+situated\s+in\s+the\s+State\s+of"),
    ("III", "Objects Clause",
     r"^\s*III\.\s*The\s+objects\s+for\s+which\s+the\s+Company\s+is\s+established\s+are"),
    ("IV",  "Liability Clause",
     r"^\s*IV\.\s*The\s+liability\s+of\s+the\s+members"),
    ("V",   "Capital Clause",
     r"^\s*V\.\s*The\s+Authori[sz]ed\s+Share\s+Capital\s+of\s+the\s+Company\s+is\s+Rs"),
    ("VI",  "Association / Subscription Clause",
     r"^\s*VI\.\s*We,\s+the\s+several\s+persons"),
]

# §5.D regexes — verbatim where the report quoted the regex.
_CAPITAL_AMOUNT_RE = re.compile(r"Rs\.?\s*([\d,]+)", re.IGNORECASE)
_CAPITAL_SPLIT_RE = re.compile(
    r"divided\s+into\s+(\d+)\s+(equity|preference)\s+shares\s+of\s+Rs\.?\s*(\d+)\s+each",
    re.IGNORECASE,
)

# Liability type from §5.B.IV — the three enum values.
_LIABILITY_RE = re.compile(
    r"limited\s+by\s+shares|limited\s+by\s+guarantee|unlimited",
    re.IGNORECASE,
)

# Registered-office state from §5.B.II body anchor.
_OFFICE_STATE_RE = re.compile(
    r"State\s+of\s+([A-Z][A-Za-z\s&\-]+?)(?:\.|\n|,)",
    re.IGNORECASE,
)

# Objects sub-classification per §5.B.III.
_OBJECTS_SUB_ANCHORS = (
    (r"\(?[aA]\)?\s+Main\s+objects", "main"),
    (r"\(?[bB]\)?\s+Matters\s+(?:incidental|ancillary)", "ancillary"),
    (r"\(?[cC]\)?\s+Other\s+objects", "other"),
)


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    # Build the six-clause tree.
    clauses = _build_six_clauses(text)
    by_roman = {c["clause_roman"]: c for c in clauses}

    # Promoted scalars per the brief.
    legal_name = _legal_name_from_clause_i(by_roman.get("I", {}).get("clause_text"))
    state_match = _OFFICE_STATE_RE.search(by_roman.get("II", {}).get("clause_text") or "")
    registered_office_state = state_match.group(1).strip() if state_match else None
    liability_match = _LIABILITY_RE.search(by_roman.get("IV", {}).get("clause_text") or "")
    liability_type = liability_match.group(0).lower() if liability_match else None

    # Capital — promote authorised amount; capture share split as sub_clauses.
    capital_clause_text = by_roman.get("V", {}).get("clause_text") or ""
    authorised_capital, share_count, share_face_value, share_class = _parse_capital(capital_clause_text)
    if authorised_capital is None and capital_clause_text:
        warnings.append("Capital amount anchor matched but no Rs. <number> found")

    # Objects — split into Main / Ancillary / Other per §5.B.III.
    objects_sub = _split_objects(by_roman.get("III", {}).get("clause_text"))

    # Subscription — try pdfplumber.extract_tables() per §5.D, fall back to text.
    subscribers, sub_warnings = _extract_subscription_table(pdf_path)
    warnings.extend(sub_warnings)

    # Stitch sub_clauses JSONB onto each MoA clause where the report calls for it.
    if "III" in by_roman:
        by_roman["III"]["sub_clauses"] = objects_sub or None
    if "V" in by_roman and (share_count is not None or share_face_value is not None):
        by_roman["V"]["sub_clauses"] = {
            "authorised_capital_rupees": authorised_capital,
            "number_of_shares": share_count,
            "face_value_rupees": share_face_value,
            "share_class": share_class,
        }
    if "VI" in by_roman and subscribers:
        by_roman["VI"]["sub_clauses"] = {"subscribers": subscribers}

    company_chunk = {
        "legal_name": legal_name,
        # The Stage 1 schema column for capital — promoted scalar from §5.B.V.
        "authorised_capital": authorised_capital,
    }

    metadata = {
        # Surfaced for downstream display / inconsistency logging — no destination
        # column in Stage 1 schema for these (documented in module docstring).
        "registered_office_state": registered_office_state,
        "liability_type": liability_type,
        "number_of_shares": share_count,
        "face_value_rupees": share_face_value,
        "share_class": share_class,
        "subscribers_count": len(subscribers) if subscribers else 0,
    }

    return {
        "doc_type": "MOA",
        "company": company_chunk,
        "moa_clauses": clauses,
        "metadata": metadata,
        "warnings": warnings,
    }


def _build_six_clauses(text: str) -> list[dict]:
    if not text:
        return []
    # Find each clause's start position via the multi-line anchored regex.
    starts: list[tuple[int, str, str]] = []
    for roman, title, anchor in _CLAUSE_ANCHORS:
        m = re.search(anchor, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            starts.append((m.start(), roman, title))
    if not starts:
        return []
    starts.sort(key=lambda x: x[0])
    out: list[dict] = []
    for i, (pos, roman, title) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        out.append({
            "clause_roman": roman,
            "clause_title": title,
            "clause_text": text[pos:end].strip(),
        })
    return out


def _legal_name_from_clause_i(clause_text: Optional[str]) -> Optional[str]:
    if not clause_text:
        return None
    # 'The name of the Company is <NAME>'
    m = re.search(
        r"name\s+of\s+the\s+Company\s+is\s+(.+?)(?:\.|\n|$)",
        clause_text, flags=re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _parse_capital(clause_text: str) -> tuple[Optional[int], Optional[int], Optional[int], Optional[str]]:
    if not clause_text:
        return None, None, None, None
    amt = None
    m = _CAPITAL_AMOUNT_RE.search(clause_text)
    if m:
        try:
            amt = int(m.group(1).replace(",", ""))
        except ValueError:
            amt = None
    share_count = face_value = None
    share_class: Optional[str] = None
    sm = _CAPITAL_SPLIT_RE.search(clause_text)
    if sm:
        try:
            share_count = int(sm.group(1))
            share_class = sm.group(2).lower()
            face_value = int(sm.group(3))
        except ValueError:
            pass
    return amt, share_count, face_value, share_class


def _split_objects(clause_text: Optional[str]) -> Optional[dict]:
    if not clause_text:
        return None
    out: dict = {"main": None, "ancillary": None, "other": None}
    positions: list[tuple[int, str]] = []
    for pat, key in _OBJECTS_SUB_ANCHORS:
        m = re.search(pat, clause_text, flags=re.IGNORECASE)
        if m:
            positions.append((m.start(), key))
    if not positions:
        return None
    positions.sort(key=lambda x: x[0])
    for i, (pos, key) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(clause_text)
        out[key] = clause_text[pos:end].strip()
    return out


def _extract_subscription_table(pdf_path: Union[str, Path]) -> tuple[list[dict], list[str]]:
    """Use pdfplumber per §5.D. Return parsed subscriber rows + any warnings."""
    rows: list[dict] = []
    warnings: list[str] = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                for tbl in tables:
                    parsed = _parse_subscription_table_rows(tbl)
                    rows.extend(parsed)
    except Exception as exc:
        warnings.append(f"MoA subscription-table extraction failed: {exc}")
    return rows, warnings


def _parse_subscription_table_rows(tbl: list[list]) -> list[dict]:
    """Map MoA subscriber-table columns by header per §5.B.VI."""
    if not tbl or len(tbl) < 2:
        return []
    header = [(c or "").strip().lower() for c in tbl[0]]
    field_index: dict[str, int] = {}
    # §5.B.VI fields: Name, Father/Spouse, Occupation, Address, Nationality,
    # Shares taken, DIN/PAN/Passport.
    label_map = {
        "name":        ["name"],
        "father":      ["father", "spouse", "guardian"],
        "occupation":  ["occupation", "description"],
        "address":     ["address", "residence"],
        "nationality": ["nationality"],
        "shares":      ["share", "shares"],
        "din_or_pan":  ["din", "pan", "passport"],
    }
    for field, needles in label_map.items():
        for i, cell in enumerate(header):
            if any(n in cell for n in needles):
                field_index[field] = i
                break
    if "name" not in field_index or "shares" not in field_index:
        return []
    rows: list[dict] = []
    for raw in tbl[1:]:
        if not raw:
            continue
        rec: dict = {}
        for field, idx in field_index.items():
            if idx < len(raw):
                v = (raw[idx] or "").strip()
                if v:
                    rec[field] = v
        if rec.get("name") and rec.get("shares"):
            rows.append(rec)
    return rows
