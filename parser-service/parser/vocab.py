"""
Controlled vocabularies for Group B extractors (Stage 3 R3).

Every constant in this module is taken verbatim from the project report
(research date 14 May 2026). Do NOT add, rename or reorder values without a
corresponding update to the report. If a parsed value doesn't match the
controlled vocabulary, the extractor logs a SOFT_WARN and stores the raw
string in metadata — it does NOT silently normalise to a closest match.
"""
from __future__ import annotations

from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# DIR-12 (report §9)
# ---------------------------------------------------------------------------

# §9.B "Purpose of filing" enum.
DIR12_PURPOSE_OF_FILING: tuple[str, ...] = (
    "Appointment",
    "Cessation",
    "Change in Designation",
    "Appointment due to disqualification of all existing directors",
    "Appointment by IRP",
    "Order of Court/NCLT/Member",
)

# §9.D "Designation" enum.
DIR12_DESIGNATION: tuple[str, ...] = (
    "Director",
    "Managing Director",
    "Whole-time Director",
    "Director and CEO",
    "Director and CFO",
    "Manager",
    "CEO",
    "CFO",
    "Company Secretary",
)

# §9.B "Category" enum.
DIR12_CATEGORY: tuple[str, ...] = (
    "Promoter",
    "Independent",
    "Nominee",
    "Additional",
    "Alternate",
    "Whole-time",
    "Managing",
    "Non-Executive",
)

# §9.B "Reason for cessation" enum.
DIR12_REASON_FOR_CESSATION: tuple[str, ...] = (
    "Resignation", "Removal", "Disqualification", "Death", "Vacation",
)


# ---------------------------------------------------------------------------
# MGT-14 (report §10)
# ---------------------------------------------------------------------------

# §10.B "Type" enum (resolution).
MGT14_RESOLUTION_TYPE: tuple[str, ...] = (
    "Special",
    "Board",
    "Ordinary",
    "Postal Ballot",
    "Winding-up under IBC s.59",
    "Resolution of liquidator",
)

# §10.B "Purpose dropdown" (the report names these specifically; trailing
# "etc." in the report is preserved as an open-ended set — off-vocab values
# log SOFT_WARN per S3-R3).
MGT14_PURPOSE: tuple[str, ...] = (
    "Alteration in object clause",
    "Alteration in name",
    "Alteration in Articles",
    "Issue of sweat equity",
    "Buy-back",
    "Loan or guarantee or security",
    "Borrowing limits",
    "RPT approval",
    "Self-prospectus",
    "Capital variation",
)


# ---------------------------------------------------------------------------
# ADT-1 (report §11)
# ---------------------------------------------------------------------------

# §11.B field 3(b) "Nature of appointment" enum.
ADT1_NATURE_OF_APPOINTMENT: tuple[str, ...] = (
    "First auditor by Board",
    "Appointment in AGM",
    "Re-appointment in AGM",
    "By C&AG",
    "Re-appointment by C&AG",
    "Casual vacancy",
    "Non-reappointment-or-removal of previous auditor",
    "By Central Govt",
    "By Tribunal",
    "Others",
)

# §11.B field I(a) auditor "Category" enum.
ADT1_AUDITOR_CATEGORY: tuple[str, ...] = ("Individual", "Firm")


# ---------------------------------------------------------------------------
# DIR-3 KYC (report §13)
# ---------------------------------------------------------------------------

# §13.B "Purpose of filing" enum.
DIR3KYC_PURPOSE_OF_FILING: tuple[str, ...] = (
    "KYC compliances",
    "Reactivation of DIN",
    "Update Mobile",
    "Update Email",
    "Update Permanent Address",
    "Update Present Address",
)


# ---------------------------------------------------------------------------
# DPT-3 (report §15)
# ---------------------------------------------------------------------------

# §15.B field 3 "Purpose of filing" enum.
DPT3_PURPOSE_OF_FILING: tuple[str, ...] = (
    "One-time return",
    "Annual Return of deposits",
    "Particulars of transactions not considered deposits",
    "Both",
)

# §15.B field 12 — Rule 2(1)(c) sub-clauses (i)–(xiii), verbatim labels.
DPT3_RULE_2_1_C_SUBCLAUSES: tuple[tuple[str, str], ...] = (
    ("i",    "CG/SG/Local/Statutory Authority"),
    ("ii",   "foreign banks/govt"),
    ("iii",  "banking company"),
    ("iv",   "loan from bank/FI/insurance"),
    ("v",    "loan from director/relative (Private Co.)"),
    ("vi",   "commercial paper"),
    ("vii",  "ICDs"),
    ("viii", "startup convertible note ≥ ₹25L single tranche"),
    ("ix",   "subscription pending allotment ≤ 60 days"),
    ("x",    "security deposit from employee ≤ annual salary"),
    ("xi",   "customer advance"),
    ("xii",  "ECB"),
    ("xiii", "others"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def match_enum(value: Optional[str], enum_values: Iterable[str]) -> Optional[str]:
    """
    Return the canonical enum value if a parsed value matches VERBATIM
    (case-insensitive equality only, with stripped surrounding whitespace
    and a trailing-punctuation tolerance for ',', ';', '.', ':').

    Returns None on no match — callers MUST log a SOFT_WARN per S3-R3 and
    stash the raw value in metadata. No prefix / fuzzy / closest-match
    fallback — silent normalisation is explicitly forbidden by the report.
    """
    if not value:
        return None
    v = value.strip().rstrip(",;.:").lower()
    for ev in enum_values:
        if ev.lower() == v:
            return ev
    return None
