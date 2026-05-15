"""
PAN Card (Company) — extractor.

Source of truth: project report §2 ('PAN Card (Company)').
Per §2.B fields: PAN (10-char, 4th=C); Name (entity name); Date of Incorporation;
ITD header 'INCOME TAX DEPARTMENT — GOVT. OF INDIA'; QR code (post-2017 e-PAN);
optional Date of issue.

Per §2.D extraction:
  - Regex ^[A-Z]{5}[0-9]{4}[A-Z]$; validate 4th = C.
  - Decode QR (pyzbar) — delimited string contains name+PAN+DOI; cross-check.
  - Anchor on 'Name' and 'Date of Incorporation'.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_pan
from parser.qr import decode_qr_codes
from pdfminer.high_level import extract_text


_ANCHOR_NAME = "Name"
_ANCHOR_DOI = "Date of Incorporation"

# PAN restricted to entity-type 'C' (Company) per §2.A: '4th character is always C for a company'.
_PAN_COMPANY_RE = re.compile(r"\b([A-Z]{3}C[A-Z][0-9]{4}[A-Z])\b")


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    # PAN — first match restricted to 4th char = C.
    pan = None
    m = _PAN_COMPANY_RE.search(text)
    if m and is_valid_pan(m.group(1)):
        pan = m.group(1)
    elif m:
        warnings.append(f"PAN anchor matched but format invalid: {m.group(1)}")

    # Name — anchor on the literal 'Name' label per §2.D.
    legal_name = _value_after_label(text, _ANCHOR_NAME)
    # DOI — anchor on 'Date of Incorporation' per §2.D.
    doi_text = _value_after_label(text, _ANCHOR_DOI)
    doi = parse_numeric_date(doi_text) if doi_text else None

    # QR cross-check per §2.D: 'delimited string contains name+PAN+DOI; cross-check'.
    decoded, qr_warnings = decode_qr_codes(pdf_path)
    warnings.extend(qr_warnings)
    qr_payload = decoded[0] if decoded else None
    qr_match = _cross_check_qr(qr_payload, pan=pan, name=legal_name, doi_iso=(doi.isoformat() if doi else None))
    if qr_payload and not qr_match:
        warnings.append("PAN QR payload did not match extracted name/PAN/DOI; using text values")

    company_chunk = {
        "pan": pan,
        "legal_name": legal_name,
        "date_of_incorporation": doi.isoformat() if doi else None,
    }
    return {
        "doc_type": "PAN_CARD",
        "company": company_chunk,
        "metadata": {"qr_payload": qr_payload, "qr_cross_check_ok": qr_match},
        "warnings": warnings,
    }


def _value_after_label(text: str, label: str, max_chars: int = 200) -> Optional[str]:
    pattern = re.compile(rf"\b{re.escape(label)}\b\s*[:\-]?\s*(.+?)(?:\n|\r|$)", re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        return None
    val = m.group(1).strip()[:max_chars]
    return val or None


def _cross_check_qr(payload: Optional[str], *, pan: Optional[str], name: Optional[str], doi_iso: Optional[str]) -> Optional[bool]:
    """Return True if the QR payload mentions all three known values; False on miss; None when no payload."""
    if not payload:
        return None
    p = payload.upper()
    checks = []
    if pan:
        checks.append(pan in p)
    if name:
        checks.append(name.upper().split()[0] in p)  # first word match — names in PAN QR vary
    if doi_iso:
        # DOI in QR may be in DD/MM/YYYY or similar — match the year only as a minimum cross-check.
        checks.append(doi_iso[:4] in p)
    if not checks:
        return None
    return all(checks)
