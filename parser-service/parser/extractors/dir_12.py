"""
DIR-12 (Appointment of Directors and KMP, and changes among them) — extractor.

Source of truth: project report §9 ('DIR-12').
Per §9.B fields:
  - Company info (CIN/Name/Reg Office/Email — auto-prefilled)
  - Purpose of filing (enum — see vocab.DIR12_PURPOSE_OF_FILING)
  - Number of persons (1-N)
  - Per-person repeating block: DIN (Director) or PAN (non-DIN KMP); Name;
    Designation; Category; DOB; Date of appointment OR cessation OR change;
    Nature of change; Reason for cessation (Resignation/Removal/
    Disqualification/Death/Vacation); Interest in other entities sub-table.
  - DSC + Practising Professional certifier.

Per §9.C layout: repeating blocks "Particulars of Director [n]" / "Director/KMP [n]".
Per §9.D extraction: DIN regex ^[0-9]{8}$; iterate "Number of persons" blocks.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from pdfminer.high_level import extract_text

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_cin, is_valid_din, is_valid_pan, is_valid_srn
from parser.vocab import (
    DIR12_CATEGORY,
    DIR12_DESIGNATION,
    DIR12_PURPOSE_OF_FILING,
    DIR12_REASON_FOR_CESSATION,
    match_enum,
)


# Word-bounded search regexes (identifiers.py constants are anchored ^...$).
_CIN_SEARCH_RE = re.compile(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b")
_DIN_SEARCH_RE = re.compile(r"\b([0-9]{8})\b")
_PAN_SEARCH_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
_SRN_SEARCH_RE = re.compile(r"\b([A-Z][0-9]{8})\b")

# Per-person repeating-block header per §9.C ("Particulars of Director [n]" /
# "Director/KMP [n]"). Both phrasings are documented in the report; we accept
# either.
_PERSON_BLOCK_RE = re.compile(
    r"(?:Particulars\s+of\s+Director|Director\s*/\s*KMP)\s*\[?(\d+)\]?\b",
    re.IGNORECASE,
)


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    cin = _first_match(_CIN_SEARCH_RE, text)
    if cin and not is_valid_cin(cin):
        cin = None

    srn = _first_match(_SRN_SEARCH_RE, text)
    if srn and not is_valid_srn(srn):
        srn = None

    company_name = _value_after_label(text, ["Company Name", "Name of the Company"])
    purpose_raw = _value_after_label(text, ["Purpose of filing"])
    purpose = match_enum(purpose_raw, DIR12_PURPOSE_OF_FILING)
    if purpose_raw and purpose is None:
        warnings.append(
            f"DIR-12 Purpose of filing value not in controlled vocabulary "
            f"(report §9.B): {purpose_raw!r}"
        )

    persons = _split_person_blocks(text)
    directors_kmp: list[dict] = []
    for block_text, block_idx in persons:
        rec, rec_warnings = _parse_person_block(block_text, block_idx, purpose)
        warnings.extend(rec_warnings)
        if rec:
            directors_kmp.append(rec)

    # Filing-level metadata for the mca_filings row.
    filed_on = _label_date(text, ["Date of filing", "Filed on"])
    fee_paid = _label_amount(text, ["Total fee", "Fee paid", "Amount paid"])

    return {
        "doc_type": "DIR_12",
        "company": {"cin": cin, "legal_name": company_name},
        "mca_filing": {
            "srn": srn,
            "form_type": "DIR-12",
            "purpose": purpose or purpose_raw,
            "filing_date": filed_on.isoformat() if filed_on else None,
            "fee_paid": fee_paid,
        },
        "directors_kmp": directors_kmp,
        "metadata": {
            "purpose_of_filing_raw": purpose_raw,
            "purpose_of_filing": purpose,
            "person_count": len(persons),
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_match(rx: re.Pattern[str], text: str) -> Optional[str]:
    m = rx.search(text)
    return m.group(1) if m else None


def _value_after_label(text: str, labels: list[str], max_chars: int = 200) -> Optional[str]:
    for label in labels:
        rx = re.compile(rf"\b{re.escape(label)}\b\s*[:\-]?\s*(.+?)(?:\n|\r|$)", re.IGNORECASE)
        m = rx.search(text)
        if m:
            v = m.group(1).strip()[:max_chars]
            if v:
                return v
    return None


def _label_date(text: str, labels: list[str]):
    raw = _value_after_label(text, labels)
    return parse_numeric_date(raw) if raw else None


def _label_amount(text: str, labels: list[str]) -> Optional[float]:
    raw = _value_after_label(text, labels)
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", raw)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _split_person_blocks(text: str) -> list[tuple[str, int]]:
    """Slice the text into one block per repeating 'Particulars of Director [n]' header."""
    if not text:
        return []
    matches = list(_PERSON_BLOCK_RE.finditer(text))
    if not matches:
        return []
    blocks: list[tuple[str, int]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block_idx = int(m.group(1))
        blocks.append((text[start:end], block_idx))
    return blocks


def _parse_person_block(block: str, block_idx: int, purpose: Optional[str]) -> tuple[Optional[dict], list[str]]:
    """Parse one 'Particulars of Director [n]' block per §9.B per-person inventory."""
    warnings: list[str] = []
    din_m = _DIN_SEARCH_RE.search(block)
    din = din_m.group(1) if din_m else None
    if din and not is_valid_din(din):
        din = None
    pan_m = _PAN_SEARCH_RE.search(block)
    pan = pan_m.group(1) if pan_m else None
    if pan and not is_valid_pan(pan):
        pan = None
    if not din and not pan:
        return None, warnings

    name = _value_after_label(block, ["Name"])
    designation_raw = _value_after_label(block, ["Designation"])
    designation = match_enum(designation_raw, DIR12_DESIGNATION)
    if designation_raw and designation is None:
        warnings.append(
            f"DIR-12 Designation value not in controlled vocabulary "
            f"(report §9.D): {designation_raw!r}"
        )

    category_raw = _value_after_label(block, ["Category"])
    category = match_enum(category_raw, DIR12_CATEGORY)
    if category_raw and category is None:
        warnings.append(
            f"DIR-12 Category value not in controlled vocabulary "
            f"(report §9.B): {category_raw!r}"
        )

    dob = _label_date(block, ["DOB", "Date of Birth"])
    appointment = _label_date(block, ["Date of appointment", "Date of Appointment"])
    cessation = _label_date(block, ["Date of cessation", "Date of Cessation"])
    reason_raw = _value_after_label(block, ["Reason for cessation"])
    reason = match_enum(reason_raw, DIR12_REASON_FOR_CESSATION)
    if reason_raw and reason is None:
        warnings.append(
            f"DIR-12 Reason for cessation value not in controlled vocabulary "
            f"(report §9.B): {reason_raw!r}"
        )

    din_or_pan = din or pan
    return {
        "din": din,
        "pan": pan,
        "din_or_pan": din_or_pan,
        "name": name,
        "designation": designation or designation_raw,
        "category": category or category_raw,
        "dob": dob.isoformat() if dob else None,
        "date_of_appointment": appointment.isoformat() if appointment else None,
        "date_of_cessation": cessation.isoformat() if cessation else None,
        # Capture the reason as part of the persisted record under 'category'
        # only when the purpose is cessation (no dedicated column for reason).
        # Kept raw in metadata for the inconsistencies log.
        "_block_index": block_idx,
        "_reason_for_cessation": reason or reason_raw,
    }, warnings
