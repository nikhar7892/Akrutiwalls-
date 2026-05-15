"""
Canonical Indian statutory identifier library.

Source of truth: project report 'Parser Specification — Indian Company &
Statutory Documents' (research date 14 May 2026), section 'Canonical
Identifier Format Reference'. Every regex, length and structural decomposition
in this file is taken verbatim from that table. Do NOT modify any pattern
without a corresponding update to the report.

Items the report flagged for sample-driven confirmation are marked
``# TODO: confirm with sample`` and listed in the report's section
'Items requiring sample-driven confirmation'.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Identifier regexes (verbatim from report identifier table).
# ---------------------------------------------------------------------------

# CIN — 21 chars. Pos 1: L/U; 2-6: NIC code; 7-8: state; 9-12: year;
# 13-15: company type (PTC/PLC/NPL/GOI/FTC/FLC/GAP/GAT/ULL/ULT/SGC);
# 16-21: 6-digit ROC reg. no.
CIN_RE = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")

# LLPIN — 7 alphanumeric. Sources differ on exact pattern.
# TODO: confirm with sample (report 'Items requiring sample-driven confirmation' #3).
LLPIN_RE = re.compile(r"^[A-Z]{3}-?[0-9]{4}$")

# FCRN — typically 'F' + 5 digits.
# TODO: confirm with sample (report 'Items requiring sample-driven confirmation' #2).
FCRN_RE = re.compile(r"^F[0-9]{5}$")

# PAN — 10 chars. 4th char encodes entity type; see PAN_ENTITY_TYPE.
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

# TAN — 10 chars. 1-3: city/RCC code; 4: first letter of deductor; 5-9: seq; 10: check.
TAN_RE = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")

# GSTIN — 15 chars. 1-2: state code (numeric 01-38); 3-12: PAN of entity;
# 13: entity code (1-9 then A-Z); 14: 'Z' for normal taxpayer; 15: Luhn-mod-36 check.
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

# DIN/DPIN — 8 numeric. Unified DIN-DPIN since MCA notification 5 July 2011.
DIN_RE = re.compile(r"^[0-9]{8}$")

# SRN — 9 alphanumeric, starting with an alphabet (A-Z) per MCA payment FAQ.
SRN_RE = re.compile(r"^[A-Z][0-9]{8}$")

# Udyam URN — 19 chars with hyphens.
UDYAM_RE = re.compile(r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$")

# IEC — same shape as PAN; post-GST IEC equals the entity's PAN.
IEC_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


# ---------------------------------------------------------------------------
# PAN 4th-char entity-type map (verbatim from report).
# ---------------------------------------------------------------------------

PAN_ENTITY_TYPE: dict[str, str] = {
    "P": "Individual",
    "C": "Company",
    "H": "HUF",
    "F": "Firm",
    "A": "AOP",
    "T": "Trust",
    "B": "BOI",
    "L": "Local Authority",
    "J": "Artificial Juridical Person",
    "G": "Government",
}


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def is_valid_cin(value: str) -> bool:
    return bool(value) and bool(CIN_RE.match(value))


def is_valid_llpin(value: str) -> bool:
    # TODO: confirm with sample (report items §3).
    return bool(value) and bool(LLPIN_RE.match(value))


def is_valid_fcrn(value: str) -> bool:
    # TODO: confirm with sample (report items §2).
    return bool(value) and bool(FCRN_RE.match(value))


def is_valid_pan(value: str) -> bool:
    return bool(value) and bool(PAN_RE.match(value))


def is_valid_tan(value: str) -> bool:
    return bool(value) and bool(TAN_RE.match(value))


def is_valid_din(value: str) -> bool:
    return bool(value) and bool(DIN_RE.match(value))


def is_valid_srn(value: str) -> bool:
    return bool(value) and bool(SRN_RE.match(value))


def is_valid_udyam(value: str) -> bool:
    return bool(value) and bool(UDYAM_RE.match(value))


def is_valid_iec(value: str, expected_pan: Optional[str] = None) -> bool:
    """IEC must match the PAN regex; if expected_pan is supplied (post-GST), it must equal that PAN."""
    if not value or not IEC_RE.match(value):
        return False
    if expected_pan is not None:
        return value == expected_pan
    return True


# ---------------------------------------------------------------------------
# GSTIN format + Luhn-mod-36 checksum
# ---------------------------------------------------------------------------
# Algorithm (verbatim from report §6.D, GST REG-06):
#   "Luhn-mod-36 over first 14 chars: each char → 0–35; alternating *1,*2;
#    sum digits per char; check = (36 − sum mod 36) mod 36."
# The report also notes (Caveats §4): "GSTIN checksum — Luhn-mod-36 is publicly
# documented (and works in practice) but not officially published by GSTN.
# Treat as best-known, not statutory."

_GSTIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_BASE = 36


def gstin_check_char(value14: str) -> Optional[str]:
    """
    Compute the expected 15th (check) character for a GSTIN given the first 14 chars.
    Returns None if the input contains a character outside [0-9A-Z].
    """
    if len(value14) < 14:
        return None
    body = value14[:14].upper()
    factor = 2
    total = 0
    for ch in reversed(body):
        if ch not in _GSTIN_CHARSET:
            return None
        digit = _GSTIN_CHARSET.index(ch)
        product = digit * factor
        # 'sum digits per char' for base-36: floor + remainder over base.
        product = (product // _GSTIN_BASE) + (product % _GSTIN_BASE)
        total += product
        factor = 1 if factor == 2 else 2
    check_value = (_GSTIN_BASE - (total % _GSTIN_BASE)) % _GSTIN_BASE
    return _GSTIN_CHARSET[check_value]


def is_valid_gstin(value: str) -> bool:
    """Format match (regex) AND Luhn-mod-36 check digit must equal position 15."""
    if not value or not GSTIN_RE.match(value):
        return False
    expected = gstin_check_char(value[:14])
    return expected is not None and expected == value[14]


# ---------------------------------------------------------------------------
# Structural decomposition (used by the cross-document validator)
# ---------------------------------------------------------------------------

@dataclass
class CinParts:
    listing_status: str   # 'L' or 'U'
    nic_code: str         # positions 2-6 (5 digits)
    state_code: str       # positions 7-8 (2 letters)
    year: int             # positions 9-12 (4 digits)
    company_type: str     # positions 13-15 (PTC/PLC/NPL/GOI/FTC/FLC/GAP/GAT/ULL/ULT/SGC)
    roc_serial: str       # positions 16-21 (6 digits)


def parse_cin(value: str) -> Optional[CinParts]:
    if not is_valid_cin(value):
        return None
    return CinParts(
        listing_status=value[0],
        nic_code=value[1:6],
        state_code=value[6:8],
        year=int(value[8:12]),
        company_type=value[12:15],
        roc_serial=value[15:21],
    )


@dataclass
class GstinParts:
    state_code: str       # positions 1-2 (numeric '01'-'38')
    pan: str              # positions 3-12
    entity_code: str      # position 13
    z: str                # position 14 (always 'Z' for normal taxpayer; varies for TDS/TCS/UIN)
    check: str            # position 15


def parse_gstin(value: str) -> Optional[GstinParts]:
    """Return structural breakdown of a *format-valid* GSTIN. Does NOT validate the check digit."""
    if not value or not GSTIN_RE.match(value):
        return None
    return GstinParts(
        state_code=value[0:2],
        pan=value[2:12],
        entity_code=value[12],
        z=value[13],
        check=value[14],
    )


@dataclass
class PanParts:
    series: str           # positions 1-3
    entity_type_code: str # position 4 (P/C/H/F/A/T/B/L/J/G)
    entity_type_label: str  # human-readable from PAN_ENTITY_TYPE
    surname_or_entity_initial: str  # position 5
    serial: str           # positions 6-9
    check: str            # position 10


def parse_pan(value: str) -> Optional[PanParts]:
    if not is_valid_pan(value):
        return None
    code = value[3]
    return PanParts(
        series=value[0:3],
        entity_type_code=code,
        entity_type_label=PAN_ENTITY_TYPE.get(code, "Unknown"),
        surname_or_entity_initial=value[4],
        serial=value[5:9],
        check=value[9],
    )


@dataclass
class TanParts:
    city_or_rcc_code: str     # positions 1-3 (e.g., BLR, DEL, MUM)
    deductor_initial: str     # position 4
    serial: str               # positions 5-9
    check: str                # position 10


def parse_tan(value: str) -> Optional[TanParts]:
    if not is_valid_tan(value):
        return None
    return TanParts(
        city_or_rcc_code=value[0:3],
        deductor_initial=value[3],
        serial=value[4:9],
        check=value[9],
    )


@dataclass
class UdyamParts:
    state_code: str   # 2 letters (e.g., MH, KA, TN)
    district_code: str  # 2 digits
    serial: str       # 7 digits


def parse_udyam(value: str) -> Optional[UdyamParts]:
    if not is_valid_udyam(value):
        return None
    parts = value.split("-")
    # UDYAM-<state>-<district>-<serial>
    return UdyamParts(state_code=parts[1], district_code=parts[2], serial=parts[3])
