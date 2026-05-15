"""
ADT-1 (Information to ROC for appointment of auditor) — extractor.

Source of truth: project report §11 ('ADT-1').
Per §11.B fields (per official MCA Instruction Kit):
  - 1(a) CIN; 1 Pre-fill (Name/Reg Office/Email)
  - 3(a) Whether falls under s.139(2) class
  - 3(b) Nature of appointment (enum — see vocab.ADT1_NATURE_OF_APPOINTMENT)
  - 4 Joint auditors? + Count
  - 5 Whether Audit Committee recommendation u/s 177 considered
  - Per-auditor repeating block I:
      (a) Category — Individual/Firm
      (b) PAN
      (c) Name
      (d) Membership No OR Firm Registration Number (FRN)
      (e) Address
      (f) Period of account — From/To date
      (g) Number of financial years for which appointed
      (h) Whether within s.141(3)(g) limit of 20 companies
      (i) Tenure of previous appointments table
  - 5(a) Whether appointed in AGM; 5(b) Date of AGM
  - 6 Date of appointment
  - 7(a) Casual vacancy? 7(b) SRN of prior ADT-1 of vacated; 7(c)-(f) vacated-auditor details
  - SRN of INC-28 — if Tribunal order
  - DSC + Resolution number + Date

Per §11.D extraction:
  - FRN regex: typical ICAI FRN ^[0-9]{6}[A-Z]$ (6 digits + region letter,
    e.g., 123456W) — verify w/ sample (carried as TODO per the report).
  - ICAI Membership No: 6 digits (occasionally 5 for older).
  - Anchor on I(a)/I(b)/I(c) labels.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from pdfminer.high_level import extract_text

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_cin, is_valid_pan, is_valid_srn
from parser.vocab import (
    ADT1_AUDITOR_CATEGORY,
    ADT1_NATURE_OF_APPOINTMENT,
    match_enum,
)


_CIN_SEARCH_RE = re.compile(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b")
_SRN_SEARCH_RE = re.compile(r"\b([A-Z][0-9]{8})\b")
_PAN_SEARCH_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
# Per §11.D ICAI FRN '^[0-9]{6}[A-Z]$' (verify w/ sample). Word-bounded for search.
# TODO: confirm with sample — carried over from the report.
_FRN_SEARCH_RE = re.compile(r"\b([0-9]{6}[A-Z])\b")
# ICAI Membership No: 6 digits (occasionally 5 for older) per §11.D.
_MEMBERSHIP_SEARCH_RE = re.compile(r"\b([0-9]{5,6})\b")

# Per-auditor block per §11.B label I (a)..(i).
_AUDITOR_BLOCK_RE = re.compile(
    r"(?:Auditor|Particulars\s+of\s+Auditor)\s*\[?(\d+)\]?\b",
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

    company_name = _value_after_label(text, ["Company Name", "Name of Company"])
    nature_raw = _value_after_label(text, ["Nature of appointment"])
    nature = match_enum(nature_raw, ADT1_NATURE_OF_APPOINTMENT)
    if nature_raw and nature is None:
        warnings.append(
            f"ADT-1 Nature of appointment not in controlled vocabulary "
            f"(report §11.B field 3(b)): {nature_raw!r}"
        )

    joint = _value_after_label(text, ["Joint auditors"])
    audit_committee = _value_after_label(text, ["Audit Committee"])
    appointed_in_agm = _value_after_label(text, ["Whether appointed in AGM"])
    date_of_agm = _label_date(text, ["Date of AGM"])
    date_of_appointment = _label_date(text, ["Date of appointment", "Date of Appointment"])

    auditor_blocks = _split_auditor_blocks(text)
    if not auditor_blocks:
        # If we couldn't find per-auditor headers, treat the whole text as one block.
        auditor_blocks = [(text, 1)]

    auditors: list[dict] = []
    for block_text, block_idx in auditor_blocks:
        rec, rec_warnings = _parse_auditor_block(
            block_text, block_idx,
            company_cin=cin,
            date_of_appointment_iso=date_of_appointment.isoformat() if date_of_appointment else None,
            agm_date_iso=date_of_agm.isoformat() if date_of_agm else None,
        )
        warnings.extend(rec_warnings)
        if rec:
            auditors.append(rec)

    filed_on = _label_date(text, ["Date of filing", "Filed on"])
    fee_paid = _label_amount(text, ["Total fee", "Fee paid"])

    return {
        "doc_type": "ADT_1",
        "company": {"cin": cin, "legal_name": company_name},
        "mca_filing": {
            "srn": srn,
            "form_type": "ADT-1",
            "purpose": f"Auditor appointment ({nature or nature_raw})" if (nature or nature_raw) else "Auditor appointment",
            "filing_date": filed_on.isoformat() if filed_on else None,
            "fee_paid": fee_paid,
        },
        "auditors": auditors,
        "metadata": {
            "nature_of_appointment": nature,
            "nature_of_appointment_raw": nature_raw,
            "joint_auditors": joint,
            "audit_committee_considered": audit_committee,
            "appointed_in_agm": appointed_in_agm,
            "auditor_count": len(auditors),
        },
        "warnings": warnings,
    }


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


def _split_auditor_blocks(text: str) -> list[tuple[str, int]]:
    matches = list(_AUDITOR_BLOCK_RE.finditer(text))
    if not matches:
        return []
    out: list[tuple[str, int]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((text[start:end], int(m.group(1))))
    return out


def _parse_auditor_block(
    block: str,
    block_idx: int,
    *,
    company_cin: Optional[str],
    date_of_appointment_iso: Optional[str],
    agm_date_iso: Optional[str],
) -> tuple[Optional[dict], list[str]]:
    warnings: list[str] = []

    # §11.B I(a) Category.
    category_raw = _value_after_label(block, ["Category"])
    category = match_enum(category_raw, ADT1_AUDITOR_CATEGORY)
    if category_raw and category is None:
        warnings.append(
            f"ADT-1 auditor Category not in controlled vocabulary "
            f"(report §11.B I(a)): {category_raw!r}"
        )

    # §11.B I(b) PAN, I(c) Name.
    pan_m = _PAN_SEARCH_RE.search(block)
    pan = pan_m.group(1) if (pan_m and is_valid_pan(pan_m.group(1))) else None
    name = _value_after_label(block, ["Name"])
    address = _value_after_label(block, ["Address"])
    email = _value_after_label(block, ["Email"])

    # §11.B I(d) Membership No OR FRN.
    frn_m = _FRN_SEARCH_RE.search(block)
    frn = frn_m.group(1) if frn_m else None
    membership = _value_after_label(block, ["Membership No", "Membership Number", "ICAI Membership"])
    if membership:
        m = _MEMBERSHIP_SEARCH_RE.search(membership)
        membership = m.group(1) if m else None

    frn_or_membership = frn or membership
    if not frn_or_membership:
        # No identifier — cannot persist this row.
        return None, warnings

    # §11.B I(f) Period of account — From / To.
    period_from = _label_date(block, ["Period of account from", "From"])
    period_to = _label_date(block, ["Period of account to", "To"])

    # §11.B I(g) Number of financial years.
    tenure_raw = _value_after_label(block, ["Number of financial years", "Tenure"])
    tenure_years = None
    if tenure_raw:
        nm = re.search(r"\d+", tenure_raw)
        tenure_years = int(nm.group(0)) if nm else None

    return {
        "category": category or category_raw,
        "name": name,
        "pan": pan,
        "icai_membership_no": membership,
        "firm_registration_no": frn,
        "frn_or_membership_no": frn_or_membership,
        "address": address,
        "email": email,
        "date_of_appointment": date_of_appointment_iso,
        "period_from": period_from.isoformat() if period_from else None,
        "period_to": period_to.isoformat() if period_to else None,
        "tenure_years": tenure_years,
        "appointment_type": None,
        "agm_date": agm_date_iso,
        "_block_index": block_idx,
    }, warnings
