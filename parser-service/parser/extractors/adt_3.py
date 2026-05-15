"""
ADT-3 (Notice of Resignation of Auditor) — extractor.

Source of truth: project report §12 ('ADT-3').
Per §12.B fields:
  1. CIN
  2. Pre-fill (Name/Reg Office/Email)
  3. Category of auditor (Individual/Firm)
  4. PAN of auditor
  5. Name
  6. Membership Number OR FRN
  7. Address
  8. Email
  9. Date of appointment
  10. Date of resignation
  11. SRN of original ADT-1 (mandatory link, 2025 amendment per G.S.R. 359(E))
  12. Reasons for resignation and other relevant facts
  - Attachments: Resignation letter (mandatory)
  - DSC: Auditor's DSC (not company)

Per §12.D extraction: label-anchored. SRN of ADT-1 validated against
^[A-Z][0-9]{8}$.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from pdfminer.high_level import extract_text

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_cin, is_valid_pan, is_valid_srn
from parser.vocab import ADT1_AUDITOR_CATEGORY, match_enum


_CIN_SEARCH_RE = re.compile(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b")
_PAN_SEARCH_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
_SRN_SEARCH_RE = re.compile(r"\b([A-Z][0-9]{8})\b")
_FRN_SEARCH_RE = re.compile(r"\b([0-9]{6}[A-Z])\b")
_MEMBERSHIP_SEARCH_RE = re.compile(r"\b([0-9]{5,6})\b")


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    cin = _first(_CIN_SEARCH_RE, text)
    if cin and not is_valid_cin(cin):
        cin = None

    # The filing's own SRN — top-of-form ADT-3 SRN. There are two SRN-shaped
    # tokens in the doc; the doc-specific SRN tends to appear in the header,
    # while the ADT-1 SRN is anchored by its label.
    adt1_srn = _value_after_label(text, ["SRN of original ADT-1", "SRN of ADT-1"])
    if adt1_srn:
        m = _SRN_SEARCH_RE.search(adt1_srn)
        adt1_srn = m.group(1) if m else None
        if adt1_srn and not is_valid_srn(adt1_srn):
            warnings.append(f"ADT-1 SRN format invalid: {adt1_srn}")
            adt1_srn = None

    # Doc-self SRN — take the first SRN-shaped token that's not the ADT-1 SRN.
    own_srn: Optional[str] = None
    for m in _SRN_SEARCH_RE.finditer(text):
        candidate = m.group(1)
        if candidate != adt1_srn and is_valid_srn(candidate):
            own_srn = candidate
            break

    company_name = _value_after_label(text, ["Company Name", "Name of Company"])
    category_raw = _value_after_label(text, ["Category of auditor", "Category"])
    category = match_enum(category_raw, ADT1_AUDITOR_CATEGORY)
    if category_raw and category is None:
        warnings.append(
            f"ADT-3 Category of auditor not in controlled vocabulary "
            f"(report §12.B field 3): {category_raw!r}"
        )

    pan_m = _PAN_SEARCH_RE.search(text)
    pan = pan_m.group(1) if (pan_m and is_valid_pan(pan_m.group(1))) else None
    name = _value_after_label(text, ["Name of auditor", "Name"])

    frn_m = _FRN_SEARCH_RE.search(text)
    frn = frn_m.group(1) if frn_m else None
    membership = _value_after_label(text, ["Membership Number", "Membership No"])
    if membership:
        mm = _MEMBERSHIP_SEARCH_RE.search(membership)
        membership = mm.group(1) if mm else None
    frn_or_membership = frn or membership

    address = _value_after_label(text, ["Address of auditor", "Address"])
    email = _value_after_label(text, ["Email"])

    date_of_appointment = _label_date(text, ["Date of appointment"])
    date_of_resignation = _label_date(text, ["Date of resignation"])
    reasons = _value_after_label(text, ["Reasons for resignation", "Reasons"])

    auditors: list[dict] = []
    if frn_or_membership:
        auditors.append({
            "category": category or category_raw,
            "name": name,
            "pan": pan,
            "icai_membership_no": membership,
            "firm_registration_no": frn,
            "frn_or_membership_no": frn_or_membership,
            "address": address,
            "email": email,
            "date_of_appointment": date_of_appointment.isoformat() if date_of_appointment else None,
            "resignation_date": date_of_resignation.isoformat() if date_of_resignation else None,
            "resignation_reason": reasons,
            "adt1_srn": adt1_srn,
            "adt3_srn": own_srn,
        })

    fee_paid = _label_amount(text, ["Total fee", "Fee paid"])

    return {
        "doc_type": "ADT_3",
        "company": {"cin": cin, "legal_name": company_name},
        "mca_filing": {
            "srn": own_srn,
            "form_type": "ADT-3",
            "purpose": "Auditor resignation",
            "filing_date": date_of_resignation.isoformat() if date_of_resignation else None,
            "fee_paid": fee_paid,
        },
        "auditors": auditors,
        "metadata": {
            "adt1_srn": adt1_srn,
        },
        "warnings": warnings,
    }


# Helpers ------------------------------------------------------------------

def _first(rx: re.Pattern[str], text: str) -> Optional[str]:
    m = rx.search(text)
    return m.group(1) if m else None


def _value_after_label(text: str, labels: list[str], max_chars: int = 400) -> Optional[str]:
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
