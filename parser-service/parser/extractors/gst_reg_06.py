"""
GST Registration Certificate (Form GST REG-06) — extractor.

Source of truth: project report §6 ('GST Registration Certificate').
Per §6.B (verbatim labels):
  - Header: 'Form GST REG-06 [See Rule 10(1)] Registration Certificate'
  - Sub-header: 'Registration Number: <GSTIN/UIN>' (15-char)
  - Note line: 'This is a system generated digitally signed Registration
    Certificate issued based on the approval of application granted on
    DD/MM/YYYY by the jurisdictional authority' OR
    '…deemed approval of application on DD/MM/YYYY'
  - 1. Legal Name
  - 2. Trade Name, if any
  - 3. Additional trade names, if any (added 2023+)
  - 4. Constitution of Business (enum)
  - 5. Address of Principal Place of Business
  - 6. Date of Liability
  - 7. Period of Validity (From, To — 'Not Applicable' for regular)
  - 8. Type of Registration (enum)
  - 9. Particulars of Approving Authority
  - 10. Date of issue of Certificate
  - Annexure A: additional places of business (Sr. No., Address)
  - Annexure B: Proprietor/Partners/Karta/Managing Director and whole-time
    Directors / Members / Designated Partners (Photo, Name, Designation,
    Resident of State, Father's Name, DOB)

Per §6.D extraction:
  - GSTIN regex + Luhn-mod-36 checksum (invoked at extraction time).
  - Anchor on numeric labels '1.', '2.', … (stable).
  - Date line regex: 'approval of application granted on (\\d{2}/\\d{2}/\\d{4})'
    or 'deemed approval of application on (\\d{2}/\\d{2}/\\d{4})'.
  - Iterate Annexure A/B rows by Sr. No.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

import pdfplumber
from pdfminer.high_level import extract_text

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_gstin, parse_gstin

# Word-bounded GSTIN search pattern (the canonical regex in identifiers.py is
# ^...$ for full-string validation, so it can't be used with .search() over
# arbitrary body text).
_GSTIN_SEARCH_RE = re.compile(
    r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b"
)


# Constitution-of-Business enum per §6.B.4 (verbatim list).
_CONSTITUTION_ENUM = (
    "Private Limited Company", "Public Limited Company", "Partnership",
    "Proprietorship", "Society-Club-Trust-AOP", "LLP", "HUF",
    "Govt Dept", "PSU", "Others",
)

# Type-of-Registration enum per §6.B.8 (verbatim list).
_TYPE_ENUM = (
    "Regular", "Composition", "Casual Taxable Person", "Non-Resident Taxable Person",
    "ISD", "TDS", "TCS", "UIN-UN Body",
)

_DATE_OF_APPROVAL_RE = re.compile(
    r"(?:approval\s+of\s+application\s+granted\s+on|deemed\s+approval\s+of\s+application\s+on)\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    # GSTIN — sub-header 'Registration Number: <GSTIN>' per §6.B.
    gstin = _extract_gstin(text)
    if gstin and not is_valid_gstin(gstin):
        # §6.D: 'Validate checksum (Luhn-mod-36)'.
        warnings.append(f"GSTIN regex matched but Luhn-mod-36 checksum failed: {gstin}")
        gstin = None

    # Numeric-label anchored fields per §6.D.
    legal_name = _value_after_numeric_label(text, "1", "Legal Name")
    trade_name = _value_after_numeric_label(text, "2", "Trade Name")
    additional_trade_names = _value_after_numeric_label(text, "3", "Additional trade names")
    constitution = _value_after_numeric_label(text, "4", "Constitution of Business")
    constitution = _normalise_enum(constitution, _CONSTITUTION_ENUM)
    principal_place = _value_after_numeric_label(text, "5", "Address of Principal Place of Business")
    date_of_liability_text = _value_after_numeric_label(text, "6", "Date of Liability")
    date_of_liability = parse_numeric_date(date_of_liability_text) if date_of_liability_text else None
    validity_text = _value_after_numeric_label(text, "7", "Period of Validity")
    validity_from, validity_to = _split_validity(validity_text)
    registration_type = _value_after_numeric_label(text, "8", "Type of Registration")
    registration_type = _normalise_enum(registration_type, _TYPE_ENUM)
    date_of_issue_text = _value_after_numeric_label(text, "10", "Date of issue of Certificate")
    date_of_issue = parse_numeric_date(date_of_issue_text) if date_of_issue_text else None

    # Date-of-approval per §6.D regex — separate from "10. Date of issue".
    date_of_approval = None
    da = _DATE_OF_APPROVAL_RE.search(text)
    if da:
        date_of_approval = parse_numeric_date(da.group(1))

    # Annexure A — additional places of business per §6.B (Sr. No., Address).
    annexure_a = _extract_annexure(pdf_path, expected_columns=("sr", "address"))
    additional_places = [row.get("address") for row in annexure_a if row.get("address")]

    # Annexure B — Proprietor/Partners/... per §6.B (Photo, Name, Designation,
    # Resident of State, Father's Name, DOB). No destination column in Stage 1
    # parser_registrations schema; surface in metadata only.
    annexure_b = _extract_annexure(
        pdf_path,
        expected_columns=("name", "designation"),
    )

    # GSTIN[3:13] cross-check vs §6.E hard-validation: produce derived PAN for
    # the persistence layer to feed into the Stage 1 cross-doc validator.
    derived_pan = None
    if gstin:
        parts = parse_gstin(gstin)
        if parts:
            derived_pan = parts.pan

    registration_chunk = {
        "type": "GST",
        # parser_registrations PK component — the GSTIN itself is the identifier.
        "identifier": gstin,
        "gstin": gstin,
        "gst_legal_name": legal_name,
        "gst_trade_name": trade_name,
        "constitution_of_business": constitution,
        "principal_place_of_business": principal_place,
        "additional_places_of_business": additional_places,
        "date_of_liability": date_of_liability.isoformat() if date_of_liability else None,
        "period_of_validity_from": validity_from.isoformat() if validity_from else None,
        "period_of_validity_to": validity_to.isoformat() if validity_to else None,
        "type_of_registration": registration_type,
    }

    company_chunk = {
        # PAN is derivable from GSTIN[3:13] per the report identifier table.
        "pan": derived_pan,
        "legal_name": legal_name,
    }

    metadata = {
        "additional_trade_names": additional_trade_names,
        "date_of_approval": date_of_approval.isoformat() if date_of_approval else None,
        "date_of_issue": date_of_issue.isoformat() if date_of_issue else None,
        "annexure_b_persons": annexure_b,
    }

    return {
        "doc_type": "GST_REG_06",
        "company": company_chunk,
        "registrations": [registration_chunk] if gstin else [],
        "metadata": metadata,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Helpers — purely internal
# ---------------------------------------------------------------------------

def _extract_gstin(text: str) -> Optional[str]:
    # Sub-header form per §6.B: 'Registration Number: <GSTIN>'.
    m = re.search(r"Registration\s+Number\s*[:\-]\s*([0-9A-Z]+)", text, re.IGNORECASE)
    if m and _GSTIN_SEARCH_RE.fullmatch(m.group(1)):
        return m.group(1)
    # Fallback: anywhere in body (e.g., header echo).
    m2 = _GSTIN_SEARCH_RE.search(text)
    return m2.group(1) if m2 else None


def _value_after_numeric_label(text: str, num: str, label: str, max_chars: int = 300) -> Optional[str]:
    """Anchor on '<num>. <label>' (numeric labels '1.','2.', … per §6.D)."""
    rx = re.compile(
        rf"^\s*{re.escape(num)}\.\s*{re.escape(label)}\b\s*[:\-]?\s*(.+?)(?=\n\s*\d{{1,2}}\.\s|\nForm\s|\Z)",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    m = rx.search(text)
    if not m:
        return None
    val = re.sub(r"\s+", " ", m.group(1).strip())[:max_chars]
    return val or None


def _normalise_enum(raw: Optional[str], enum_values: tuple[str, ...]) -> Optional[str]:
    if not raw:
        return None
    for v in enum_values:
        if v.lower() in raw.lower():
            return v
    return raw  # Preserve original — caller may log a soft warning.


def _split_validity(text: Optional[str]) -> tuple[Optional["object"], Optional["object"]]:
    if not text:
        return None, None
    if "not applicable" in text.lower() or "n/a" in text.lower():
        return None, None
    # 'From DD/MM/YYYY To DD/MM/YYYY' style.
    m = re.search(r"From\s+(\d{2}/\d{2}/\d{4}).*?To\s+(\d{2}/\d{2}/\d{4})", text,
                  re.IGNORECASE | re.DOTALL)
    if m:
        return parse_numeric_date(m.group(1)), parse_numeric_date(m.group(2))
    return None, None


def _extract_annexure(pdf_path: Union[str, Path], expected_columns: tuple[str, ...]) -> list[dict]:
    """Iterate every page's tables; pick rows whose header contains all expected_columns."""
    out: list[dict] = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                for tbl in page.extract_tables() or []:
                    rows = _parse_annexure_rows(tbl, expected_columns)
                    out.extend(rows)
    except Exception:
        return out
    return out


def _parse_annexure_rows(tbl: list[list], expected_columns: tuple[str, ...]) -> list[dict]:
    if not tbl or len(tbl) < 2:
        return []
    header = [(c or "").strip().lower() for c in tbl[0]]
    if not all(any(needle in cell for cell in header) for needle in expected_columns):
        return []
    # Build column index per needle (first match wins).
    column_index: dict[str, int] = {}
    needles = ("sr", "address", "name", "designation", "father", "dob", "resident", "photo")
    for needle in needles:
        for i, cell in enumerate(header):
            if needle in cell:
                column_index[needle] = i
                break
    rows: list[dict] = []
    for raw in tbl[1:]:
        if not raw:
            continue
        rec: dict = {}
        for needle, idx in column_index.items():
            if idx < len(raw):
                v = (raw[idx] or "").strip()
                if v:
                    rec[needle] = v
        if any(rec.get(k) for k in ("address", "name")):
            rows.append(rec)
    return rows
