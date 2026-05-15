"""
DPT-3 (Return of Deposits / Particulars of transactions not considered as
deposits) — extractor.

Source of truth: project report §15 ('DPT-3').
Per §15.B fields:
  1(a) CIN; 1 Pre-fill
  2 Type of company (Private/Public)
  3 Purpose of filing (controlled vocab — vocab.DPT3_PURPOSE_OF_FILING)
  4 Whether IFSC public co. / private co. eligible to accept deposits
  5 Whether accepted deposits from public (+ particulars)
  6 Objects of company (brief)
  7 Net Worth as per latest audited BS (as on 31 March)
  8(a) Period for which return is filed (FY start/end)
  8(b) Date of last closing of accounts
  9 Credit rating particulars (agency, rating, date)
  10 Total number of deposit holders
  11 Particulars of deposits (repeating)
  12 Particulars of receipts not considered deposits as on 31 March under
     Rule 2(1)(c) — (i) … (xiii) per vocab.DPT3_RULE_2_1_C_SUBCLAUSES.
  13 Charge particulars
  14 Liquid assets particulars

Per §15.D extraction: 'Amounts in absolute INR; strip commas. Anchor on
Rule 2(1)(c) sub-clause numbers (i–xiii).'
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from pdfminer.high_level import extract_text

from parser.dates import parse_numeric_date
from parser.identifiers import is_valid_cin, is_valid_srn
from parser.vocab import (
    DPT3_PURPOSE_OF_FILING,
    DPT3_RULE_2_1_C_SUBCLAUSES,
    match_enum,
)


_CIN_SEARCH_RE = re.compile(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b")
_SRN_SEARCH_RE = re.compile(r"\b([A-Z][0-9]{8})\b")
# Sub-clause numbering per §15.B field 12 — Roman numerals i–xiii.
_RULE2_1C_RE = re.compile(
    r"\(([ivx]+)\)\s+([A-Za-z][^\n]{0,180})",
)


def extract(pdf_path: Union[str, Path]) -> dict:
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    cin = _first(_CIN_SEARCH_RE, text)
    if cin and not is_valid_cin(cin):
        cin = None
    srn = _first(_SRN_SEARCH_RE, text)
    if srn and not is_valid_srn(srn):
        srn = None

    company_name = _value_after_label(text, ["Company Name", "Name of Company"])
    company_type = _value_after_label(text, ["Type of company"])
    purpose_raw = _value_after_label(text, ["Purpose of filing"])
    purpose = match_enum(purpose_raw, DPT3_PURPOSE_OF_FILING)
    if purpose_raw and purpose is None:
        warnings.append(
            f"DPT-3 Purpose of filing not in controlled vocabulary "
            f"(report §15.B field 3): {purpose_raw!r}"
        )

    objects = _value_after_label(text, ["Objects of company"])
    net_worth = _label_amount(text, ["Net Worth", "Net worth"])
    fy_period = _value_after_label(text, ["Period for which return is filed", "FY"])
    fy = _normalise_fy(fy_period)
    date_bs_closing = _label_date(text, ["Date of last closing of accounts"])

    credit_agency = _value_after_label(text, ["Credit rating agency", "Agency"])
    credit_rating = _value_after_label(text, ["Credit rating", "Rating"])

    total_deposit_holders = _label_int(text, ["Total number of deposit holders"])

    outstanding_secured = _label_amount(text, ["Outstanding Secured", "Secured outstanding"])
    outstanding_unsecured = _label_amount(text, ["Outstanding Unsecured", "Unsecured outstanding"])
    outstanding_non_deposit = _label_amount(text, ["Outstanding non-deposit", "Non-deposit outstanding"])

    # Field 12 — Rule 2(1)(c) sub-clauses (i–xiii). Iterate per §15.D.
    rule_2_1_c = _parse_rule_2_1_c(text)
    if rule_2_1_c:
        seen_keys = {row["sub_clause"] for row in rule_2_1_c}
        expected_keys = {k for k, _ in DPT3_RULE_2_1_C_SUBCLAUSES}
        missing = sorted(expected_keys - seen_keys)
        if missing:
            warnings.append(
                f"DPT-3 Rule 2(1)(c) sub-clauses missing from text: "
                f"{', '.join(missing)} (report §15.B field 12)"
            )

    deposits = []
    if fy and cin:
        deposits.append({
            "financial_year": fy,
            "purpose_of_filing": purpose or purpose_raw,
            "outstanding_secured": outstanding_secured,
            "outstanding_unsecured": outstanding_unsecured,
            "outstanding_non_deposit": outstanding_non_deposit,
            "net_worth": net_worth,
            "credit_rating": (f"{credit_agency or ''} {credit_rating or ''}".strip() or None),
            "dpt3_srn": srn,
        })

    filed_on = _label_date(text, ["Date of filing", "Filed on"])
    fee_paid = _label_amount(text, ["Total fee", "Fee paid"])

    return {
        "doc_type": "DPT_3",
        "company": {"cin": cin, "legal_name": company_name},
        "mca_filing": {
            "srn": srn,
            "form_type": "DPT-3",
            "purpose": purpose or purpose_raw,
            "filing_date": filed_on.isoformat() if filed_on else None,
            "fee_paid": fee_paid,
        },
        "deposits": deposits,
        "metadata": {
            "purpose_of_filing": purpose,
            "purpose_of_filing_raw": purpose_raw,
            "company_type": company_type,
            "objects_of_company": objects,
            "fy_period_raw": fy_period,
            "fy": fy,
            "balance_sheet_closing_date": date_bs_closing.isoformat() if date_bs_closing else None,
            "total_deposit_holders": total_deposit_holders,
            "rule_2_1_c_breakdown": rule_2_1_c,
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


def _label_int(text: str, labels: list[str]) -> Optional[int]:
    raw = _value_after_label(text, labels)
    if not raw:
        return None
    m = re.search(r"\d+", raw)
    return int(m.group(0)) if m else None


def _normalise_fy(value: Optional[str]) -> Optional[str]:
    """Map 'FY 2023-24', '01/04/2023 - 31/03/2024', '2023-2024' → '2023-24'."""
    if not value:
        return None
    m = re.search(r"(\d{4})\s*[-/]\s*(\d{2,4})", value)
    if m:
        start, end = m.group(1), m.group(2)
        if len(end) == 4:
            end = end[2:]
        return f"{start}-{end}"
    return value.strip()


def _parse_rule_2_1_c(text: str) -> list[dict]:
    """Iterate the Rule 2(1)(c) sub-clauses (i)..(xiii) per §15.B field 12."""
    out: list[dict] = []
    seen: set[str] = set()
    for m in _RULE2_1C_RE.finditer(text):
        key = m.group(1).lower()
        if key in seen or key not in {k for k, _ in DPT3_RULE_2_1_C_SUBCLAUSES}:
            continue
        seen.add(key)
        body = m.group(2).strip()
        # Pull a trailing amount if present.
        amt_m = re.search(r"([\d,]+(?:\.\d{1,2})?)", body)
        amt = None
        if amt_m:
            try:
                amt = float(amt_m.group(1).replace(",", ""))
            except ValueError:
                amt = None
        out.append({"sub_clause": key, "description": body, "amount": amt})
    return out
