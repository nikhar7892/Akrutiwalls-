"""
MCA Master Data (printout) — extractor.

Source of truth: project report §8 ('MCA Master Data').
Per §8.B field groups:
  - Company Information: CIN, Company Name, ROC Code (e.g., RoC-Mumbai),
    Registration Number (last 6 of CIN), Company Category (limited by shares /
    by guarantee / unlimited), Company Sub-Category (Indian Non-Govt /
    State Govt / Union Govt / Subsidiary of Foreign Co.), Class of Company
    (Private/Public), Date of Incorporation, Age, Activity (NIC + description)
  - Registered Office: Address, Email ID, Whether Listed (Yes/No),
    Suspended at Stock Exchange
  - Capital Details: Authorised Capital, Paid-up Capital, Number of Members
  - Compliance: Date of Last AGM, Date of Balance Sheet, Company Status
    (Active / Active in Progress / Strike Off / Under Liquidation / Dormant /
     Amalgamated / Dissolved)
  - Charges (Index of Charges view): Charge ID, Creation Date, Modification
    Date, Closure Date, Assets under charge, Charge amount
  - Directors / Signatory Details (View Signatory Details view): DIN, Name,
    Designation, Date of Appointment, Date of Cessation

Per §8.D extraction: 'Anchor on exact label strings. Status enums are exact
strings. Strip ₹/commas from capital amounts.' Per §8.E display: 'Treat as
authoritative for current status, last-AGM/last-BS dates, current capital,
current directors. Hard-flag if company_status != "Active".'
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

import pdfplumber
from pdfminer.high_level import extract_text

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_cin, is_valid_din


# Word-bounded search regexes (identifiers.py constants are anchored ^...$).
_CIN_SEARCH_RE = re.compile(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b")


# Status enum per §8.B (verbatim).
_STATUS_ENUM = (
    "Active", "Active in Progress", "Strike Off", "Under Liquidation",
    "Dormant", "Amalgamated", "Dissolved",
)
_LISTED_ENUM = ("Yes", "No", "Unlisted", "Listed")


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    # CIN — only one on the page.
    cin = None
    cm = _CIN_SEARCH_RE.search(text)
    if cm and is_valid_cin(cm.group(1)):
        cin = cm.group(1)

    company_name = _value_after_label(text, ["Company Name"])
    roc_code = _value_after_label(text, ["RoC-Code", "ROC Code", "ROC-Code"])
    registration_no = _value_after_label(text, ["Registration Number", "Registration No"])
    company_category = _value_after_label(text, ["Company Category"])
    company_sub_category = _value_after_label(text, ["Company Sub Category", "Company SubCategory"])
    class_of_company = _value_after_label(text, ["Class of Company"])
    date_of_incorporation = _label_date(text, ["Date of Incorporation"])

    # Registered Office.
    registered_office_address = _value_after_label(text, ["Address of Registered Office"])
    registered_office_email = _value_after_label(text, ["Email Id", "Email ID", "Email"])
    listed_raw = _value_after_label(text, ["Whether Listed or not", "Whether Listed"])
    listing_status = _normalise_listing(listed_raw)

    # Capital — strip ₹ / commas per §8.D.
    authorised_capital = _capital_amount(text, ["Authori[sz]ed Capital(?:\\(Rs\\))?", "Authori[sz]ed Capital"])
    paid_up_capital = _capital_amount(text, ["Paid[\\s\\-]?up Capital(?:\\(Rs\\))?", "Paid[\\s\\-]?up Capital"])

    # Compliance.
    last_agm_date = _label_date(text, ["Date of Last AGM"])
    last_bs_date = _label_date(text, ["Date of Balance Sheet"])
    company_status = _enum_value(text, ["Company Status"], _STATUS_ENUM)

    # Activity (NIC + description) per §8.B.
    activity_raw = _value_after_label(text, ["Activity"])
    nic_industry_code, industrial_activity_description = _split_activity(activity_raw)

    # Directors / Signatory Details — table at the bottom per §8.B.
    directors = _extract_directors_table(pdf_path)

    company_chunk = {
        "cin": cin,
        "legal_name": company_name,
        "roc_jurisdiction": roc_code,
        # Stage 1 schema doesn't have a separate registration_number column; the
        # report's Consolidated Master Schema lacks it. Surface in metadata only.
        "company_category": company_category,
        "company_sub_category": company_sub_category,
        "listing_status": listing_status,
        "company_status": company_status,
        "registered_office_address": registered_office_address,
        "registered_office_email": registered_office_email,
        "authorised_capital": authorised_capital,
        "paid_up_capital": paid_up_capital,
        "nic_industry_code": nic_industry_code,
        "industrial_activity_description": industrial_activity_description,
        "date_of_incorporation": date_of_incorporation.isoformat() if date_of_incorporation else None,
        "last_agm_date": last_agm_date.isoformat() if last_agm_date else None,
        "last_balance_sheet_date": last_bs_date.isoformat() if last_bs_date else None,
    }

    # Promote the Class column into our parser_company.company_category if the
    # report's column isn't already populated above. The report explicitly
    # separates 'Class of Company' (Private/Public) from 'Company Category'
    # (limited by shares / by guarantee / unlimited) — so they're DIFFERENT
    # columns. We surface 'class_of_company' in metadata.
    metadata = {
        "registration_number": registration_no,
        "class_of_company": class_of_company,
        "is_active": (company_status == "Active") if company_status else None,
    }

    return {
        "doc_type": "MCA_MASTER_DATA",
        "company": company_chunk,
        "directors_kmp": directors,
        "metadata": metadata,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _value_after_label(text: str, labels: list[str], max_chars: int = 300) -> Optional[str]:
    for label in labels:
        rx = re.compile(rf"\b{label}\b\s*[:\-]?\s*(.+?)(?:\n|\r|$)", re.IGNORECASE)
        m = rx.search(text)
        if m:
            v = m.group(1).strip()[:max_chars]
            if v:
                return v
    return None


def _label_date(text: str, labels: list[str]) -> Optional["object"]:
    raw = _value_after_label(text, labels)
    return parse_numeric_date(raw) if raw else None


def _normalise_listing(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    r = raw.strip().lower()
    if r in ("yes", "listed"):
        return "Listed"
    if r in ("no", "unlisted"):
        return "Unlisted"
    return raw.strip()


def _enum_value(text: str, labels: list[str], enum_values: tuple[str, ...]) -> Optional[str]:
    raw = _value_after_label(text, labels)
    if not raw:
        return None
    for ev in enum_values:
        if ev.lower() == raw.strip().lower() or ev.lower() in raw.lower():
            return ev
    return raw


def _capital_amount(text: str, labels: list[str]) -> Optional[int]:
    """Strip ₹/commas per §8.D and parse to int."""
    raw = _value_after_label(text, labels)
    if not raw:
        return None
    cleaned = re.sub(r"[₹,Rs.\s]", "", raw)
    m = re.search(r"(\d+)", cleaned)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _split_activity(raw: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Activity field is 'NIC <code> - <description>' or similar per §8.B."""
    if not raw:
        return None, None
    m = re.search(r"(?:NIC\s*)?(\d{2,5})\s*[-–:]\s*(.+)", raw)
    if m:
        return m.group(1), m.group(2).strip()
    return None, raw.strip()


def _extract_directors_table(pdf_path: Union[str, Path]) -> list[dict]:
    """Iterate the 'View Signatory Details' table per §8.B."""
    out: list[dict] = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                for tbl in page.extract_tables() or []:
                    rows = _parse_signatory_rows(tbl)
                    out.extend(rows)
    except Exception:
        return out
    return out


def _parse_signatory_rows(tbl: list[list]) -> list[dict]:
    if not tbl or len(tbl) < 2:
        return []
    header = [(c or "").strip().lower() for c in tbl[0]]
    # Required columns per §8.B: DIN, Name, Designation, Date of Appointment, Date of Cessation.
    column_index: dict[str, int] = {}
    for needle, key in (
        ("din",         "din"),
        ("name",        "name"),
        ("designation", "designation"),
        ("appointment", "date_of_appointment"),
        ("cessation",   "date_of_cessation"),
    ):
        for i, cell in enumerate(header):
            if needle in cell:
                column_index[key] = i
                break
    if "din" not in column_index or "name" not in column_index:
        return []
    out: list[dict] = []
    for raw in tbl[1:]:
        if not raw:
            continue
        rec: dict = {}
        for key, idx in column_index.items():
            if idx < len(raw):
                v = (raw[idx] or "").strip()
                if not v:
                    continue
                if key.startswith("date"):
                    d = parse_numeric_date(v)
                    rec[key] = d.isoformat() if d else None
                else:
                    rec[key] = v
        din = rec.get("din")
        if not din or not is_valid_din(din):
            # Skip rows where the DIN column isn't a real DIN.
            continue
        # Materialised PK helper for parser_directors_kmp.
        rec["din_or_pan"] = din
        out.append(rec)
    return out
