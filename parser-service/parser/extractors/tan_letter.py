"""
TAN Allotment Letter — extractor.

Source of truth: project report §3 ('TAN Allotment Letter').
Per §3.B fields: TAN (10-char); Deductor name; Date of allotment; Address;
Category of deductor; PAN of deductor; AO Code (Area, Type, Range, AO Number);
14-digit Acknowledgement number of underlying Form 49B; Issuing authority footer.

Per §3.D extraction: Regex ^[A-Z]{4}[0-9]{5}[A-Z]$. TAN appears after
'TAN' / 'Tax Deduction Account Number' heading.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_pan, is_valid_tan
from pdfminer.high_level import extract_text


_ANCHOR_TAN_HEADING_LONG = "Tax Deduction Account Number"
_ANCHOR_TAN_HEADING_SHORT = "TAN"

_TAN_RE = re.compile(r"\b([A-Z]{4}[0-9]{5}[A-Z])\b")
_PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
# 14-digit acknowledgement of underlying Form 49B per §3.B.
_ACK_RE = re.compile(r"\b(\d{14})\b")
# Date of allotment — typical numeric date.
_DATE_RE = re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b")
# Category enum per §3.B (verbatim list):
# Company / Branch of Company / Statutory body / Firm / Individual / HUF / AOP / etc.
_CATEGORY_RE = re.compile(
    r"\b(Company|Branch of Company|Statutory body|Firm|Individual|HUF|AOP)\b",
    re.IGNORECASE,
)
# AO Code group (4-part) per §3.B: Area Code, AO Type, Range Code, AO Number.
_AO_BLOCK_RE = re.compile(
    r"AO\s*Code[\s:]*?(?P<area>[A-Z]{1,4})\s+(?P<type>[A-Z])\s+(?P<range>[A-Z0-9]+)\s+(?P<num>\d+)",
    re.IGNORECASE,
)


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    # Anchor on the long form first, fallback to short form per §3.D.
    tan = _take_after_heading(text, [_ANCHOR_TAN_HEADING_LONG, _ANCHOR_TAN_HEADING_SHORT], _TAN_RE)
    if tan and not is_valid_tan(tan):
        warnings.append(f"TAN format invalid: {tan}")
        tan = None

    # PAN of deductor anywhere in the body.
    pan_m = _PAN_RE.search(text)
    pan = pan_m.group(1) if (pan_m and is_valid_pan(pan_m.group(1))) else None

    # Deductor name — heuristic based on label per §3.C ('addressee block').
    deductor_name = _value_after_label(text, "Name of (?:the\\s+)?Deductor")
    if deductor_name is None:
        deductor_name = _value_after_label(text, "Deductor")

    # Address per §3.C.
    address = _value_after_label(text, "Address")

    # Date of allotment per §3.B.
    date_text = _value_after_label(text, "Date of (?:Allotment|allotment)")
    date_of_allotment = parse_numeric_date(date_text) if date_text else None
    if date_of_allotment is None:
        m = _DATE_RE.search(text)
        if m:
            date_of_allotment = parse_numeric_date(m.group(1))

    category_m = _CATEGORY_RE.search(text)
    category = category_m.group(1) if category_m else None

    ao_block = None
    ao_m = _AO_BLOCK_RE.search(text)
    if ao_m:
        ao_block = {
            "area_code": ao_m.group("area").upper(),
            "ao_type": ao_m.group("type").upper(),
            "range_code": ao_m.group("range").upper(),
            "ao_number": ao_m.group("num"),
        }

    ack_m = _ACK_RE.search(text)
    acknowledgement = ack_m.group(1) if ack_m else None

    company_chunk = {
        # Promoted to parser_company
        "tan": tan,
        "pan": pan,
        "legal_name": deductor_name,
    }

    metadata = {
        "address": address,
        "date_of_allotment": date_of_allotment.isoformat() if date_of_allotment else None,
        "category": category,
        "ao_code": ao_block,
        "form_49b_acknowledgement": acknowledgement,
    }

    return {
        "doc_type": "TAN_LETTER",
        "company": company_chunk,
        "metadata": metadata,
        "warnings": warnings,
    }


def _take_after_heading(text: str, headings: list[str], value_re: "re.Pattern[str]") -> Optional[str]:
    for h in headings:
        idx = text.lower().find(h.lower())
        if idx < 0:
            continue
        tail = text[idx + len(h) : idx + len(h) + 200]
        m = value_re.search(tail)
        if m:
            return m.group(1)
    # Last resort — anywhere in body.
    m = value_re.search(text)
    return m.group(1) if m else None


def _value_after_label(text: str, label_pattern: str, max_chars: int = 200) -> Optional[str]:
    rx = re.compile(rf"\b{label_pattern}\b\s*[:\-]?\s*(.+?)(?:\n|\r|$)", re.IGNORECASE)
    m = rx.search(text)
    if not m:
        return None
    val = m.group(1).strip()[:max_chars]
    return val or None
