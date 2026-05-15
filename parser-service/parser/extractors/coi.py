"""
Certificate of Incorporation (Form INC-11) — extractor.

Source of truth: project report §1 ('Certificate of Incorporation (Form INC-11)').
Field inventory verbatim from §1.B; extraction guidance from §1.D.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from parser.dates import parse_coi_words_date, parse_numeric_date
from parser.dsc import extract_signer_name
from parser.identifiers import is_valid_cin, is_valid_pan, is_valid_tan
from pdfminer.high_level import extract_text


# Anchors per report §1.D — verbatim phrases.
_ANCHOR_CIN = "Corporate Identity Number (CIN)"
_ANCHOR_PAN = "Permanent Account Number (PAN)"

# Constitution regex per report §1.D — verbatim alternation.
_CONSTITUTION_RE = re.compile(r"limited by shares|limited by guarantee|unlimited company",
                              re.IGNORECASE)

# CIN / PAN / TAN regexes — re-stated locally for clarity, but match the report's
# identifier table verbatim and ARE the same as parser/identifiers.py.
_CIN_RE = re.compile(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b")
_PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
_TAN_RE = re.compile(r"\b([A-Z]{4}[0-9]{5}[A-Z])\b")

# Body-text pattern per report §1.C — captures company name between two literal
# phrases: "I hereby certify that <NAME> is incorporated on this".
_BODY_NAME_RE = re.compile(
    r"I\s+hereby\s+certify\s+that\s+(.+?)\s+is\s+incorporated\s+on\s+this",
    re.IGNORECASE | re.DOTALL,
)

# Issuing officer + place of issue per §1.B fields 8 and 9.
_ISSUER_RE = re.compile(
    r"(Assistant|Deputy|Joint)?\s*Registrar\s+of\s+Companies",
    re.IGNORECASE,
)
_PLACE_RE = re.compile(
    r"Place\s*[:\-]\s*([A-Za-z][A-Za-z\s.\-]+?)(?:\n|$)",
    re.IGNORECASE,
)


def extract(pdf_path: Union[str, Path]) -> dict:
    """Extract COI fields per report §1. Returns the company chunk + warnings."""
    text = extract_text(str(pdf_path)) or ""
    warnings: list[str] = []

    # Per §1.D: anchor on "Corporate Identity Number (CIN)" then take next CIN-shaped token.
    cin = _take_next(text, _ANCHOR_CIN, _CIN_RE)
    if cin and not is_valid_cin(cin):
        warnings.append(f"COI anchor matched but CIN format invalid: {cin}")
        cin = None

    pan = _take_next(text, _ANCHOR_PAN, _PAN_RE)
    if pan and not is_valid_pan(pan):
        warnings.append(f"COI anchor matched but PAN format invalid: {pan}")
        pan = None

    # Per §1.B field 4: "TAN ... usually communicated via covering email, not on COI face".
    # We try anyway — if present, lift it.
    tan_match = _TAN_RE.search(text)
    tan = tan_match.group(1) if (tan_match and is_valid_tan(tan_match.group(1))) else None

    # Per §1.D: name = substring between "I hereby certify that" and "is incorporated on this".
    legal_name = None
    name_m = _BODY_NAME_RE.search(text)
    if name_m:
        legal_name = name_m.group(1).strip()

    # Per §1.D: words-to-date parser for "FIFTH day of APRIL two thousand twenty four".
    doi = parse_coi_words_date(text)
    if doi is None:
        # Some COI prints use a numeric date in the cover line; try as a fallback.
        # Report §1.B field 6 says 'Date of incorporation in words and figures'.
        m = re.search(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b", text)
        if m:
            doi = parse_numeric_date(m.group(1))

    # Constitution per §1.D regex.
    constitution_m = _CONSTITUTION_RE.search(text)
    constitution = constitution_m.group(0).lower() if constitution_m else None

    # Issuing officer + place of issue per §1.B fields 8/9.
    issuer_m = _ISSUER_RE.search(text)
    issuer = issuer_m.group(0).strip() if issuer_m else None
    place_m = _PLACE_RE.search(text)
    place_of_issue = place_m.group(1).strip() if place_m else None

    # DSC signer name per §1.D — non-fatal.
    signer, dsc_warnings = extract_signer_name(pdf_path)
    warnings.extend(dsc_warnings)

    company_chunk: dict = {
        # Columns mapped to parser_company.
        "cin": cin,
        "pan": pan,
        "tan": tan,
        "legal_name": legal_name,
        "date_of_incorporation": doi.isoformat() if doi else None,
    }

    # Metadata block — info captured by the report but not persisted to the
    # parser_company column set (no destination column). Surface to caller for
    # display / inconsistency logging only.
    metadata: dict = {
        "constitution": constitution,
        "issuing_officer": issuer,
        "place_of_issue": place_of_issue,
        "dsc_signer": signer,
    }

    return {
        "doc_type": "COI",
        "company": company_chunk,
        "metadata": metadata,
        "warnings": warnings,
    }


def _take_next(text: str, anchor: str, value_re: "re.Pattern[str]") -> Optional[str]:
    """Find the anchor; return the first regex match in the trailing window."""
    idx = text.lower().find(anchor.lower())
    if idx < 0:
        return None
    tail = text[idx + len(anchor) : idx + len(anchor) + 200]
    m = value_re.search(tail)
    return m.group(1) if m else None
