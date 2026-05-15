"""
Document classifier — identifies which of the 15 report-defined document types
a PDF is, by matching the title constants / header anchors named in each
document's section of the project report.

The 15 types and their anchors are encoded below. Group A (1-8) extractors
land in Stage 2; Group B (9-15) extractors land in Stage 3 — the classifier
returns the type for both groups so Stage 3 only needs to wire extractors,
not classification logic.

V2-vs-V3 detection (report 'MCA V3 PDF Specifics — Parsing Notes' §8): the
report-stated visual signal is a blue 'Ministry of Corporate Affairs' band on
V3 vs the older Devanagari emblem on V2. Since we are label-anchored only,
we proxy by checking for V3-specific text markers per form. When neither is
distinguishable, we return ``portal_version=None`` — Stage 3 extractors will
default to V3 (Lot-3 cutover effective 14 July 2025).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Union


class DocType(str, Enum):
    # Group A — Stage 2
    COI = "COI"
    PAN_CARD = "PAN_CARD"
    TAN_LETTER = "TAN_LETTER"
    AOA = "AOA"
    MOA = "MOA"
    GST_REG_06 = "GST_REG_06"
    UDYAM = "UDYAM"
    MCA_MASTER_DATA = "MCA_MASTER_DATA"
    # Group B — Stage 3 (classifier only in Stage 2)
    DIR_12 = "DIR_12"
    MGT_14 = "MGT_14"
    ADT_1 = "ADT_1"
    ADT_3 = "ADT_3"
    DIR_3_KYC = "DIR_3_KYC"
    SRN_CHALLAN = "SRN_CHALLAN"
    DPT_3 = "DPT_3"


class PortalVersion(str, Enum):
    V2 = "V2"
    V3 = "V3"


@dataclass
class ClassifyResult:
    doc_type: Optional[DocType]
    portal_version: Optional[PortalVersion] = None
    matched_anchor: Optional[str] = None
    confidence: str = "none"   # 'high' | 'medium' | 'none'
    raw_text_length: int = 0


# ---------------------------------------------------------------------------
# Title / header anchor table — one entry per doc, in priority order.
# Each anchor is the verbatim string from the report's section for that doc.
# Most-specific anchors first so we never misclassify SRN Challan as DIR-12.
# ---------------------------------------------------------------------------

# Each entry: (doc_type, anchor_string, [optional] additional_predicate)
_AnchorPred = Callable[[str], bool]


def _and(*preds: _AnchorPred) -> _AnchorPred:
    return lambda s: all(p(s) for p in preds)


def _contains(needle: str) -> _AnchorPred:
    n = needle.lower()
    return lambda s: n in s.lower()


def _regex(pattern: str) -> _AnchorPred:
    rx = re.compile(pattern, re.IGNORECASE)
    return lambda s: bool(rx.search(s))


# Anchors taken VERBATIM from the report sections referenced in comments.
# Group A — Stage 2 extractor targets.
_RULES_GROUP_A: list[tuple[DocType, str, _AnchorPred]] = [
    # §1 COI: title constant
    (DocType.COI,
     "Certificate of Incorporation [Pursuant to sub-section (2) of section 7 of the Companies Act, 2013",
     _contains("Certificate of Incorporation [Pursuant to sub-section (2) of section 7 of the Companies Act, 2013")),
    # §6 GST REG-06: header constant
    (DocType.GST_REG_06,
     "Form GST REG-06 [See Rule 10(1)] Registration Certificate",
     _contains("Form GST REG-06")),
    # §8 MCA Master Data: page heading from MCA21 V3 menu path
    (DocType.MCA_MASTER_DATA,
     "Company/LLP Master Data",
     _contains("Company/LLP Master Data")),
    # §7 Udyam: face title + URN format presence
    (DocType.UDYAM,
     "Udyam Registration Certificate",
     _and(_contains("Udyam Registration"),
          _regex(r"\bUDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}\b"))),
    # §5 MoA: cover-page title (case-insensitive contains)
    (DocType.MOA,
     "MEMORANDUM OF ASSOCIATION OF",
     _contains("MEMORANDUM OF ASSOCIATION OF")),
    # §4 AoA: first-page header
    (DocType.AOA,
     "ARTICLES OF ASSOCIATION OF",
     _contains("ARTICLES OF ASSOCIATION OF")),
    # §3 TAN Allotment Letter — checked BEFORE PAN_CARD because TAN letters
    # also carry the 'Income Tax Department' header. The 'Tax Deduction Account
    # Number' phrase is unique to TAN letters per §3.D.
    (DocType.TAN_LETTER,
     "Tax Deduction Account Number",
     _and(_contains("Tax Deduction Account Number"),
          _regex(r"\b[A-Z]{4}[0-9]{5}[A-Z]\b"))),
    # §2 PAN Card: ITD header + 'Permanent Account Number' phrase + PAN-with-4th=C.
    # The 'Permanent Account Number' phrase distinguishes the PAN card from a TAN
    # letter whose body also references PAN.
    (DocType.PAN_CARD,
     "INCOME TAX DEPARTMENT",
     _and(_contains("INCOME TAX DEPARTMENT"),
          _contains("Permanent Account Number"),
          # PAN regex restricted to 4th char = C (Company)
          _regex(r"\b[A-Z]{3}C[A-Z][0-9]{4}[A-Z]\b"))),
]

# Group B — classifier hooks only (Stage 3 extractors).
# Form-name anchors per the report sections (§9 DIR-12, §10 MGT-14, §11 ADT-1,
# §12 ADT-3, §13 DIR-3 KYC, §14 SRN Challan, §15 DPT-3).
_RULES_GROUP_B: list[tuple[DocType, str, _AnchorPred]] = [
    # SRN Challan: per §14.C, "Ministry of Corporate Affairs — Government of India"
    # header + "SRN" label top-left + "Service Description" / "Form Name" line.
    # Distinguished from filed-form acknowledgements by the absence of form
    # body sections (e.g. no per-person director blocks).
    (DocType.SRN_CHALLAN,
     "Service Description",
     _and(_contains("Ministry of Corporate Affairs"),
          _contains("Service Description"),
          _regex(r"\b[A-Z][0-9]{8}\b"))),
    (DocType.DIR_12, "Form DIR-12",
     _regex(r"\bForm\s+(?:No\.?\s*)?DIR-12\b")),
    (DocType.DIR_3_KYC, "Form DIR-3 KYC",
     _regex(r"\bForm\s+(?:No\.?\s*)?DIR-3\s*KYC\b")),
    (DocType.MGT_14, "Form MGT-14",
     _regex(r"\bForm\s+(?:No\.?\s*)?MGT-14\b")),
    (DocType.ADT_1, "Form ADT-1",
     _regex(r"\bForm\s+(?:No\.?\s*)?ADT-1\b")),
    (DocType.ADT_3, "Form ADT-3",
     _regex(r"\bForm\s+(?:No\.?\s*)?ADT-3\b")),
    (DocType.DPT_3, "Form DPT-3",
     _regex(r"\bForm\s+(?:No\.?\s*)?DPT-3\b")),
]


def classify_text(text: str) -> ClassifyResult:
    """Run the rule list over already-extracted PDF text."""
    if not text:
        return ClassifyResult(doc_type=None)
    raw_len = len(text)

    for doc_type, anchor, pred in _RULES_GROUP_A + _RULES_GROUP_B:
        if pred(text):
            portal = _detect_portal_version(doc_type, text)
            return ClassifyResult(
                doc_type=doc_type,
                portal_version=portal,
                matched_anchor=anchor,
                confidence="high",
                raw_text_length=raw_len,
            )
    return ClassifyResult(doc_type=None, raw_text_length=raw_len)


def classify(pdf_path: Union[str, Path]) -> ClassifyResult:
    """Classify a PDF file by reading its text layer and running ``classify_text``."""
    text = _extract_text(pdf_path)
    return classify_text(text)


def _extract_text(pdf_path: Union[str, Path]) -> str:
    """Concatenate every page's text via pdfminer.six (per report Stage 1 toolchain)."""
    try:
        from pdfminer.high_level import extract_text
        return extract_text(str(pdf_path)) or ""
    except Exception:
        # Fall back to pdfplumber so a corrupt PDF still gets a try.
        try:
            import pdfplumber
            parts: list[str] = []
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page in pdf.pages:
                    parts.append(page.extract_text() or "")
            return "\n".join(parts)
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# V2 vs V3 portal-version detection (report §'MCA V3 PDF Specifics — Parsing
# Notes' §8). Visual signal not available; we use text proxies. Stage 3
# extractors call into this for routing.
# ---------------------------------------------------------------------------

# Forms migrated to V3 with the 14 July 2025 Lot-3 cutover (per ICSI Lot-3 FAQ
# quoted in report Key Findings §7). Group A docs predominantly stay on V2/web
# UI for MCA Master Data (browser print).
_V3_TEXT_MARKERS: dict[DocType, list[str]] = {
    # Per report §11 ADT-1: "Audit Committee question at field 5".
    DocType.ADT_1: ["Audit Committee", "5 Whether Audit Committee", "5 Whether Audit Committee"],
    # Per report §13 DIR-3 KYC: "purpose dropdown added".
    DocType.DIR_3_KYC: ["Purpose of filing", "KYC compliances", "Reactivation of DIN"],
    # DIR-12 V3: Purpose options expanded — anchor on the post-V3 enum text.
    DocType.DIR_12: ["Appointment due to disqualification", "Appointment by IRP"],
    # MGT-14 V3 has the "Postal Ballot" purpose option in some contexts; lacking
    # a more specific report-stated marker, we leave portal_version unspecified
    # for MGT-14 today and let Stage 3 default to V3.
}


def _detect_portal_version(doc_type: DocType, text: str) -> Optional[PortalVersion]:
    """Return V3 if a V3-specific marker is present, V2 if a clearly-V2 marker
    is present, else None (let downstream default to V3 per Lot-3 cutover)."""
    markers = _V3_TEXT_MARKERS.get(doc_type)
    if markers:
        lt = text.lower()
        if any(m.lower() in lt for m in markers):
            return PortalVersion.V3
    # No reliable V2 marker available without sample inspection; return None.
    # TODO: confirm with sample (V2 emblem text fallback for MCA forms).
    return None
