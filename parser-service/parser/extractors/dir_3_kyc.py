"""
DIR-3 KYC (KYC of Directors) — extractor.

Source of truth: project report §13 ('DIR-3 KYC'). As amended by Companies
(Appointment and Qualification of Directors) Amendment Rules, 2025 notified
vide G.S.R. 943(E) dated 31 December 2025, effective 31 March 2026 — KYC
moves from annual to triennial. Per PIB Press Release PRID=2210552 cited
in §13.A: directors who filed KYC at least once before 31 March 2026 have
their next KYC filing due by **30 June 2028**.

Per §13.B (eForm) fields:
  1. DIN (pre-filled)
  2. First/Middle/Last name (as per PAN)
  3. Father's first/middle/last name
  4. Nationality (dropdown)
  5. Whether citizen of India
  6. Whether resident in India
  7. DOB (must be ≥ 18 years from system date)
  8. Gender
  9. Income-tax PAN
  10. Whether has Aadhaar
  10(a) Aadhaar Number (12 digits, conditional)
  10(b) Name as per Aadhaar
  11. If no Aadhaar: Voter ID / Passport / DL number
  12. Passport number (mandatory for foreigners)
  13. Personal mobile (OTP-verified)
  14. Personal email (OTP-verified)
  15. Permanent residential address
  16. Whether present residence same as permanent
  17. Present residential address (conditional)
  - Purpose of filing (controlled vocab — vocab.DIR3KYC_PURPOSE_OF_FILING)

Per §13.D extraction: Mask Aadhaar (store last 4). Split names by PAN match.
Anchor on labels.

S3-R2 triennial due-date logic implemented in ``compute_kyc_due_date``.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional, Union

from pdfminer.high_level import extract_text

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_cin, is_valid_din, is_valid_pan, is_valid_srn
from parser.vocab import DIR3KYC_PURPOSE_OF_FILING, match_enum


# Triennial regime effective date per G.S.R. 943(E) dated 31 December 2025
# (effective 31 March 2026). Per PIB PRID=2210552: directors who completed KYC
# before that date have next KYC due 30 June 2028.
KYC_TRIENNIAL_EFFECTIVE = date(2026, 3, 31)
KYC_TRANSITIONAL_DUE = date(2028, 6, 30)


def compute_kyc_due_date(kyc_last_filed_date: Optional[date]) -> Optional[date]:
    """
    Per S3-R2:
      - filed BEFORE 2026-03-31  → next due 2028-06-30
      - filed ON OR AFTER 2026-03-31 → +3 years (exact-date)
    """
    if kyc_last_filed_date is None:
        return None
    if kyc_last_filed_date < KYC_TRIENNIAL_EFFECTIVE:
        return KYC_TRANSITIONAL_DUE
    # Triennial cycle from the last filing date. TODO: confirm with sample —
    # the within-cycle due-date convention is not explicit in the report.
    try:
        return kyc_last_filed_date.replace(year=kyc_last_filed_date.year + 3)
    except ValueError:
        # Feb 29 fallback.
        return kyc_last_filed_date.replace(month=2, day=28, year=kyc_last_filed_date.year + 3)


_CIN_SEARCH_RE = re.compile(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b")
_DIN_SEARCH_RE = re.compile(r"\b([0-9]{8})\b")
_PAN_SEARCH_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
_SRN_SEARCH_RE = re.compile(r"\b([A-Z][0-9]{8})\b")
# Aadhaar masked per §13.D: store only last 4 digits. Common renderings:
# "XXXXXXXX1234", "********1234", "xxxx xxxx 1234".
_AADHAAR_LAST4_RE = re.compile(r"(?:[xX*]{4,12}|[xX*]{4}\s*[xX*]{4}\s*)\s*([0-9]{4})\b")


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    cin = _first(_CIN_SEARCH_RE, text)
    if cin and not is_valid_cin(cin):
        cin = None
    srn = _first(_SRN_SEARCH_RE, text)
    if srn and not is_valid_srn(srn):
        srn = None

    din_m = _DIN_SEARCH_RE.search(text)
    din = din_m.group(1) if din_m else None
    if din and not is_valid_din(din):
        din = None

    pan = None
    pan_m = _PAN_SEARCH_RE.search(text)
    if pan_m and is_valid_pan(pan_m.group(1)):
        pan = pan_m.group(1)

    purpose_raw = _value_after_label(text, ["Purpose of filing"])
    purpose = match_enum(purpose_raw, DIR3KYC_PURPOSE_OF_FILING)
    if purpose_raw and purpose is None:
        warnings.append(
            f"DIR-3 KYC Purpose of filing not in controlled vocabulary "
            f"(report §13.B): {purpose_raw!r}"
        )

    name = _value_after_label(text, ["Name"])
    father_name = _value_after_label(text, ["Father's name", "Father Name", "Father's Name"])
    nationality = _value_after_label(text, ["Nationality"])
    is_citizen = _value_after_label(text, ["citizen of India", "Whether citizen of India"])
    is_resident = _value_after_label(text, ["resident in India", "Whether resident in India"])
    dob = _label_date(text, ["DOB", "Date of Birth"])
    gender = _value_after_label(text, ["Gender"])
    mobile = _value_after_label(text, ["Mobile", "Personal mobile"])
    email = _value_after_label(text, ["Email", "Personal email"])
    permanent_addr = _value_after_label(text, ["Permanent residential address", "Permanent address"])
    present_addr = _value_after_label(text, ["Present residential address", "Present address"])
    passport_no = _value_after_label(text, ["Passport number", "Passport No"])

    aadhaar_last4 = None
    am = _AADHAAR_LAST4_RE.search(text)
    if am:
        aadhaar_last4 = am.group(1)

    kyc_last_filed = _label_date(text, ["Date of filing", "Filed on"])
    kyc_due = compute_kyc_due_date(kyc_last_filed)

    if not din:
        # Without a DIN there's no key to upsert the director against.
        warnings.append("DIR-3 KYC has no extractable DIN — director row cannot be updated.")
        directors_kmp: list[dict] = []
    else:
        directors_kmp = [{
            "din": din,
            "din_or_pan": din,
            "pan": pan,
            "name": name,
            "father_name": father_name,
            "nationality": nationality,
            "dob": dob.isoformat() if dob else None,
            "gender": gender,
            "mobile": mobile,
            "email": email,
            "address_permanent": permanent_addr,
            "address_present": present_addr,
            "passport_no": passport_no,
            "aadhaar_last4": aadhaar_last4,
            "kyc_last_filed_date": kyc_last_filed.isoformat() if kyc_last_filed else None,
            "kyc_due_date": kyc_due.isoformat() if kyc_due else None,
            # Flags surfaced for the inconsistencies log via metadata:
            "_is_citizen_of_india": is_citizen,
            "_is_resident_in_india": is_resident,
        }]

    return {
        "doc_type": "DIR_3_KYC",
        "company": {"cin": cin},
        "mca_filing": {
            "srn": srn,
            "form_type": "DIR-3 KYC",
            "purpose": purpose or purpose_raw or "KYC compliances",
            "filing_date": kyc_last_filed.isoformat() if kyc_last_filed else None,
        },
        "directors_kmp": directors_kmp,
        "metadata": {
            "purpose_of_filing": purpose,
            "purpose_of_filing_raw": purpose_raw,
            "din": din,
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
