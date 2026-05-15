"""
Udyam (MSME) Registration Certificate — extractor.

Source of truth: project report §7 ('MSME / Udyam Registration Certificate').
Per §7.B fields: URN ('UDYAM-XX-00-0000000'); Name of Enterprise; Type of
Enterprise (Micro/Small/Medium); Date of incorporation/registration; Date of
commencement; Major activity (Manufacturing/Services); NIC codes (repeating);
Social category; Gender; Owner/Director details (Name + masked Aadhaar
'XXXXXXXX1234' + mobile + email); Official Address; Mobile; Email; Date of
Udyam Registration; Number of Persons Employed (optional); Bank details
(optional); DIC, MSME-DI; PAN of Enterprise; GSTIN(s) (one per State); QR code
linking to portal verification.

Per §7.B note: 'Investment in plant & machinery and annual turnover are NOT
printed on the face — the only enterprise-size signal on the face is the
Type of Enterprise enum.'

Per §7.D extraction:
  - URN regex ^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$.
  - Decode QR (should point to udyamregistration.gov.in/UA/...).
  - Aadhaar masked: store only last 4 digits.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_gstin, is_valid_pan
from parser.qr import decode_qr_codes
from pdfminer.high_level import extract_text


# Word-bounded search regexes (the identifiers.py constants are anchored
# ^...$ for full-string validation, not search use).
_UDYAM_SEARCH_RE = re.compile(r"\b(UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7})\b")
_PAN_SEARCH_RE   = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
_GSTIN_SEARCH_RE = re.compile(r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b")


# Type-of-Enterprise enum per §7.B (verbatim).
_TYPE_ENUM = ("Micro", "Small", "Medium")
# Major activity enum per §7.B (verbatim).
_ACTIVITY_ENUM = ("Manufacturing", "Services")
# Aadhaar masked per §7.B/§7.D — 'XXXXXXXX1234' style.
_AADHAAR_MASKED_RE = re.compile(r"\b(?:[xX]{4,12}|\*{4,12})\s*([0-9]{4})\b")


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    # URN per §7.D regex.
    urn = None
    m = _UDYAM_SEARCH_RE.search(text)
    if m:
        urn = m.group(1)

    enterprise_name = _value_after_label(text, ["Name of Enterprise", "Enterprise Name"])
    enterprise_type = _enum_in_text(text, ["Type of Enterprise", "Enterprise Type"], _TYPE_ENUM)
    activity = _enum_in_text(text, ["Major Activity", "Activity"], _ACTIVITY_ENUM)

    # Date fields per §7.B.
    date_of_registration = _label_date(text, ["Date of Udyam Registration", "Date of Registration"])
    date_of_commencement = _label_date(text, ["Date of Commencement"])
    date_of_incorporation = _label_date(text, ["Date of Incorporation/Registration", "Date of Incorporation"])

    # NIC codes — repeating list per §7.B.
    nic_codes = _extract_nic_codes(text)

    # Owner Aadhaar — masked, last 4 only per §7.D.
    aadhaar_last4 = None
    am = _AADHAAR_MASKED_RE.search(text)
    if am:
        aadhaar_last4 = am.group(1)

    # PAN of enterprise + GSTIN(s) per §7.B.
    pan = None
    pm = _PAN_SEARCH_RE.search(text)
    if pm and is_valid_pan(pm.group(1)):
        pan = pm.group(1)
    gstins: list[str] = []
    for gm in _GSTIN_SEARCH_RE.finditer(text):
        v = gm.group(1)
        if is_valid_gstin(v) and v not in gstins:
            gstins.append(v)

    # QR per §7.D — should point to udyamregistration.gov.in/UA/... Non-fatal.
    qr_payloads, qr_warnings = decode_qr_codes(pdf_path)
    warnings.extend(qr_warnings)
    qr_ok = any("udyamregistration.gov.in" in (p or "").lower() for p in qr_payloads)

    # Owner / address contact details per §7.B.
    address = _value_after_label(text, ["Official Address", "Address"])
    mobile = _value_after_label(text, ["Mobile"])
    email = _value_after_label(text, ["Email"])

    registration_chunk = {
        "type": "UDYAM",
        "identifier": urn,
        "udyam_registration_number": urn,
        "udyam_enterprise_type": enterprise_type,
        "udyam_date_of_registration": date_of_registration.isoformat() if date_of_registration else None,
        "udyam_date_of_commencement": date_of_commencement.isoformat() if date_of_commencement else None,
        "nic_codes": nic_codes,
    }

    company_chunk = {
        "pan": pan,
        "legal_name": enterprise_name,
        "date_of_incorporation": date_of_incorporation.isoformat() if date_of_incorporation else None,
    }

    metadata = {
        "major_activity": activity,
        "owner_aadhaar_last4": aadhaar_last4,
        "address": address,
        "mobile": mobile,
        "email": email,
        "linked_gstins": gstins,
        "qr_payloads": qr_payloads,
        "qr_points_to_udyam_portal": qr_ok,
    }

    return {
        "doc_type": "UDYAM",
        "company": company_chunk,
        "registrations": [registration_chunk] if urn else [],
        "metadata": metadata,
        "warnings": warnings,
    }


def _value_after_label(text: str, labels: list[str], max_chars: int = 200) -> Optional[str]:
    for label in labels:
        rx = re.compile(rf"\b{re.escape(label)}\b\s*[:\-]?\s*(.+?)(?:\n|\r|$)", re.IGNORECASE)
        m = rx.search(text)
        if m:
            v = m.group(1).strip()[:max_chars]
            if v:
                return v
    return None


def _enum_in_text(text: str, labels: list[str], enum_values: tuple[str, ...]) -> Optional[str]:
    val = _value_after_label(text, labels)
    if not val:
        return None
    for ev in enum_values:
        if ev.lower() in val.lower():
            return ev
    return val  # Preserve raw — caller may log soft-warn.


def _label_date(text: str, labels: list[str]) -> Optional["object"]:
    raw = _value_after_label(text, labels)
    if not raw:
        return None
    return parse_numeric_date(raw)


def _extract_nic_codes(text: str) -> list[str]:
    """NIC codes per §7.B — 2-digit/4-digit/5-digit + activity description."""
    codes: list[str] = []
    seen: set[str] = set()
    # NIC label area; capture digit groups appearing in the NIC section.
    rx = re.compile(r"\bNIC\b[^\n]{0,200}", re.IGNORECASE)
    chunks: list[str] = []
    for m in rx.finditer(text):
        chunks.append(m.group(0))
    body = "\n".join(chunks) if chunks else text
    for dm in re.finditer(r"\b(\d{2,5})\b", body):
        v = dm.group(1)
        if 2 <= len(v) <= 5 and v not in seen:
            seen.add(v)
            codes.append(v)
    return codes
