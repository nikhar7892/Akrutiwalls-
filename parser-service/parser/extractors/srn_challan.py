"""
SRN Challan (MCA Payment Challan / Receipt / Acknowledgement) — extractor.

Source of truth: project report §14 ('SRN Challan').
Per §14.B fields:
  - Header "Ministry of Corporate Affairs — Government of India" + MCA logo
  - SRN (top-left, 9-char)
  - Date of generation
  - Service Description / Form Name (e.g., "Form DIR-12")
  - CIN/LLPIN
  - Company name
  - User/signatory name
  - Amount paid (Filing fee / Stamp duty / Additional fee / Total)
  - Currency "INR"
  - Mode of payment (Online — Card/Net Banking/UPI; Offline — NEFT; Pay Later)
  - Payment status (Paid/Not Paid/Pending)
  - Transaction/Reference ID (online); UTR & UTN (NEFT); Bank name (offline)
  - Challan expiry date (unpaid)
  - Authorised signatory text
  - Footer "computer-generated receipt does not require signature"

Per §14.C: SRN top-left ALWAYS. Per §14.D: regex ^[A-Z][0-9]{8}$; extract
top-left first; cross-check by "SRN" label.

Persistence: one parser_mca_filings row only (no child rows). The challan is
the canonical write path for the filing's payment fields.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from pdfminer.high_level import extract_text

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_cin, is_valid_srn


_CIN_SEARCH_RE = re.compile(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b")
_SRN_SEARCH_RE = re.compile(r"\b([A-Z][0-9]{8})\b")

# §14.B Payment status enum (verbatim labels).
_PAYMENT_STATUS_VALUES = ("Paid", "Not Paid", "Pending")
# §14.B Mode of payment enum (verbatim).
_PAYMENT_MODE_VALUES = (
    "Card", "Net Banking", "UPI", "NEFT", "Pay Later",
)


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    # Per §14.D: "Extract top-left first; cross-check by 'SRN' label."
    srn = _extract_srn_top_left(text)
    if srn and not is_valid_srn(srn):
        warnings.append(f"SRN format invalid: {srn}")
        srn = None

    cin = _first(_CIN_SEARCH_RE, text)
    if cin and not is_valid_cin(cin):
        cin = None

    company_name = _value_after_label(text, ["Company Name", "Name of Company"])
    form_name = _value_after_label(text, ["Service Description", "Form Name"])
    date_of_generation = _label_date(text, ["Date of Generation", "Date of generation"])
    user_name = _value_after_label(text, ["User Name", "Signatory Name"])

    filing_fee = _label_amount(text, ["Filing fee"])
    stamp_duty = _label_amount(text, ["Stamp duty"])
    additional_fee = _label_amount(text, ["Additional fee"])
    total_amount = _label_amount(text, ["Total", "Amount paid"])

    payment_mode = _first_enum(text, _PAYMENT_MODE_VALUES)
    payment_status = _first_enum(text, _PAYMENT_STATUS_VALUES)
    transaction_id = _value_after_label(text, ["Transaction ID", "Reference ID"])
    utr = _value_after_label(text, ["UTR"])
    utn = _value_after_label(text, ["UTN"])
    bank_name = _value_after_label(text, ["Bank Name"])
    expiry = _label_date(text, ["Challan expiry date", "Expiry Date"])

    return {
        "doc_type": "SRN_CHALLAN",
        "company": {"cin": cin, "legal_name": company_name},
        "mca_filing": {
            "srn": srn,
            "form_type": _normalise_form_type(form_name),
            "purpose": form_name,
            "filing_date": date_of_generation.isoformat() if date_of_generation else None,
            "fee_paid": (filing_fee or 0.0) + (stamp_duty or 0.0) if (filing_fee is not None or stamp_duty is not None) else total_amount,
            "additional_fee": additional_fee,
            "payment_mode": payment_mode,
            "payment_status": payment_status,
        },
        "metadata": {
            "form_name_raw": form_name,
            "user_name": user_name,
            "transaction_id": transaction_id,
            "utr": utr,
            "utn": utn,
            "bank_name": bank_name,
            "challan_expiry": expiry.isoformat() if expiry else None,
            "total_amount": total_amount,
        },
        "warnings": warnings,
    }


# Helpers ------------------------------------------------------------------

def _first(rx: re.Pattern[str], text: str) -> Optional[str]:
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


def _first_enum(text: str, values: tuple[str, ...]) -> Optional[str]:
    lt = text.lower()
    for v in values:
        if v.lower() in lt:
            return v
    return None


def _extract_srn_top_left(text: str) -> Optional[str]:
    """
    Per §14.C: SRN top-left ALWAYS. We pull the first SRN-shaped token in the
    text — pdfminer reads pages top-to-bottom left-to-right, so the top-left
    SRN is the first match. Cross-checked by 'SRN' label if present.
    """
    label_value = _value_after_label(text, ["SRN"])
    if label_value:
        m = _SRN_SEARCH_RE.search(label_value)
        if m:
            return m.group(1)
    m = _SRN_SEARCH_RE.search(text)
    return m.group(1) if m else None


def _normalise_form_type(form_name: Optional[str]) -> Optional[str]:
    """Map 'Form DIR-12' → 'DIR-12' for storage in parser_mca_filings.form_type."""
    if not form_name:
        return None
    m = re.search(
        r"(INC-\d+|DIR-\d+(?:\s*KYC)?|MGT-\d+|ADT-\d+|DPT-\d+|SH-\d+|PAS-\d+|AOC-\d+|FC-\d+)",
        form_name,
        re.IGNORECASE,
    )
    return m.group(1).upper().replace(" ", " ") if m else form_name.strip()
