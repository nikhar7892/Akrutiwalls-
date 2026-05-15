"""
MGT-14 (Filing of Resolutions and Agreements to ROC) — extractor.

Source of truth: project report §10 ('MGT-14').
Per §10.B fields:
  - Company info
  - Purpose: Resolution / Agreement / Both
  - Number of resolutions
  - Per-resolution block: Type (controlled vocab — see vocab.MGT14_RESOLUTION_TYPE);
    Section under Companies Act; Sub-section; Purpose dropdown (controlled vocab —
    see vocab.MGT14_PURPOSE); Date of resolution; Place of meeting
  - Per-agreement block: Type / Section / Purpose / Date / Parties
  - SRN of INC-28 — if filing beyond 300 days (condonation path).
  - Attachments: Certified true copy + Explanatory statement / Altered MoA / Altered AoA / Agreement copy.

Per §10.C: repeating blocks numbered. Per §10.D: build controlled-vocab tagger;
section regex 'Section\\s+(\\d+)(?:\\(([0-9a-z]+)\\))?'; if purpose=Alteration in
object clause, capture new CIN.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from pdfminer.high_level import extract_text

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_cin, is_valid_srn
from parser.vocab import (
    MGT14_PURPOSE,
    MGT14_RESOLUTION_TYPE,
    match_enum,
)


_CIN_SEARCH_RE = re.compile(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b")
_SRN_SEARCH_RE = re.compile(r"\b([A-Z][0-9]{8})\b")

# §10.D verbatim: 'Section\s+(\d+)(?:\(([0-9a-z]+)\))?'.
_SECTION_RE = re.compile(r"Section\s+(\d+)(?:\(([0-9a-z]+)\))?", re.IGNORECASE)

# Per-resolution block header. §10.C says "Repeating blocks numbered" without
# a single canonical phrase; the V3 form prints "Resolution [n]" headers.
_RESOLUTION_BLOCK_RE = re.compile(
    r"(?:Resolution|Particulars\s+of\s+Resolution)\s*\[?(\d+)\]?\b",
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

    company_name = _value_after_label(text, ["Company Name"])
    inc28_srn = _value_after_label(text, ["SRN of INC-28"])
    if inc28_srn and not is_valid_srn(inc28_srn.split()[0]):
        # The label may yield a longer string; pull only the SRN-shaped substring.
        m = _SRN_SEARCH_RE.search(inc28_srn)
        inc28_srn = m.group(1) if m else None

    blocks = _split_resolution_blocks(text)
    resolutions: list[dict] = []
    for block_text, idx in blocks:
        rec, rec_warnings = _parse_resolution_block(block_text, idx)
        warnings.extend(rec_warnings)
        if rec:
            resolutions.append(rec)

    filed_on = _label_date(text, ["Date of filing", "Filed on"])
    fee_paid = _label_amount(text, ["Total fee", "Fee paid"])

    return {
        "doc_type": "MGT_14",
        "company": {"cin": cin, "legal_name": company_name},
        "mca_filing": {
            "srn": srn,
            "form_type": "MGT-14",
            "purpose": "Filing of resolutions and agreements (s.117)",
            "filing_date": filed_on.isoformat() if filed_on else None,
            "fee_paid": fee_paid,
        },
        "resolutions": resolutions,
        "metadata": {
            "inc28_srn": inc28_srn,
            "resolution_count": len(resolutions),
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_match(rx: re.Pattern[str], text: str) -> Optional[str]:
    m = rx.search(text)
    return m.group(1) if m else None


def _value_after_label(text: str, labels: list[str], max_chars: int = 250) -> Optional[str]:
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


def _split_resolution_blocks(text: str) -> list[tuple[str, int]]:
    matches = list(_RESOLUTION_BLOCK_RE.finditer(text))
    if not matches:
        return []
    out: list[tuple[str, int]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((text[start:end], int(m.group(1))))
    return out


def _parse_resolution_block(block: str, idx: int) -> tuple[Optional[dict], list[str]]:
    warnings: list[str] = []

    type_raw = _value_after_label(block, ["Type"])
    resolution_type = match_enum(type_raw, MGT14_RESOLUTION_TYPE)
    if type_raw and resolution_type is None:
        warnings.append(
            f"MGT-14 Resolution Type not in controlled vocabulary "
            f"(report §10.B): {type_raw!r}"
        )

    purpose_raw = _value_after_label(block, ["Purpose"])
    purpose = match_enum(purpose_raw, MGT14_PURPOSE)
    if purpose_raw and purpose is None:
        warnings.append(
            f"MGT-14 Purpose dropdown value not in controlled vocabulary "
            f"(report §10.B): {purpose_raw!r}"
        )

    section_m = _SECTION_RE.search(block)
    section_under = None
    if section_m:
        section_no = section_m.group(1)
        sub = section_m.group(2)
        section_under = f"s.{section_no}" + (f"({sub})" if sub else "")

    date_passed = _label_date(block, ["Date of resolution", "Date of Resolution", "Date passed"])
    meeting_date = _label_date(block, ["Date of meeting", "Meeting date"])
    meeting_type = _value_after_label(block, ["Place of meeting", "Meeting type"])

    if not any([resolution_type, purpose, section_under, date_passed]):
        # Block lacks any signal — skip to avoid empty rows.
        return None, warnings

    return {
        "sequence": idx,
        "resolution_type": resolution_type or type_raw,
        "section_under": section_under,
        "purpose": purpose or purpose_raw,
        "date_passed": date_passed.isoformat() if date_passed else None,
        "meeting_type": meeting_type,
        "meeting_date": meeting_date.isoformat() if meeting_date else None,
    }, warnings
