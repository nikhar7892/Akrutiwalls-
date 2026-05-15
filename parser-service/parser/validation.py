"""
Cross-Document Validation Matrix.

Source of truth: project report 'Parser Specification — Indian Company &
Statutory Documents', section 'Cross-Document Validation Matrix'. The
matrix is encoded literally below — each rule mirrors one row of the report.

Stage 1 deliverable: this is the validator skeleton. It defines the issue
shape, the severity enum, the per-rule callables and the one-shot orchestrator
``validate_company_record(...)``. The Stage 2/3 per-document extractors will
hand it parsed payloads grouped by source name.

Source-name vocabulary used throughout (kept tight, taken from the report):
    "COI"                   — Certificate of Incorporation (Form INC-11)
    "PAN_CARD"              — Company PAN card / e-PAN
    "TAN_LETTER"            — TAN allotment letter
    "AOA"                   — Articles of Association
    "MOA"                   — Memorandum of Association
    "GST_REG_06"            — GST Registration Certificate (Form GST REG-06)
    "UDYAM"                 — Udyam / MSME Registration Certificate
    "MCA_MASTER_DATA"       — MCA21 V3 Master Data printout
    "DIR_12"                — DIR-12 filing
    "MGT_14"                — MGT-14 filing
    "ADT_1"                 — ADT-1 filing
    "ADT_3"                 — ADT-3 filing
    "DIR_3_KYC"             — DIR-3 KYC filing
    "SRN_CHALLAN"           — SRN Challan / Receipt
    "DPT_3"                 — DPT-3 filing
    "AOC_4" / "MGT_7"       — annual filings (referenced in the auditor / capital rules)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional

from parser.identifiers import parse_cin, parse_gstin


# ---------------------------------------------------------------------------
# Severity & issue shape
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    HARD_FAIL = "hard_fail"
    SOFT_WARN = "soft_warn"


@dataclass
class ValidationIssue:
    severity: Severity
    field: str
    message: str
    sources: list[str] = field(default_factory=list)
    expected: Optional[str] = None
    actual: Optional[str] = None
    rule: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_name(name: Optional[str]) -> str:
    """For soft-warn legal-name comparison. Case + whitespace + punctuation tolerance."""
    if not name:
        return ""
    cleaned = name.strip().upper()
    # Collapse whitespace and strip trailing punctuation that varies between sources.
    import re
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.rstrip(".,;:")
    return cleaned


def _present(by_source: dict[str, Optional[str]]) -> dict[str, str]:
    """Return only the (source, value) pairs where value is non-empty."""
    return {s: str(v).strip() for s, v in by_source.items() if v not in (None, "")}


def _all_equal(values: Iterable[str]) -> bool:
    seen = set(values)
    return len(seen) <= 1


# ---------------------------------------------------------------------------
# Rule 1 — CIN (HARD FAIL)
# Sources: COI, GST REG-06 (Annexure B), MCA Master Data, every MCA filing.
# ---------------------------------------------------------------------------

def validate_cin_consistency(cins: dict[str, Optional[str]]) -> list[ValidationIssue]:
    """
    `cins`: mapping source-name → CIN extracted from that source.
    Hard-fail if two sources disagree on a non-empty CIN.
    """
    present = _present(cins)
    if len(present) < 2:
        return []
    if _all_equal(present.values()):
        return []
    return [
        ValidationIssue(
            severity=Severity.HARD_FAIL,
            field="cin",
            sources=sorted(present.keys()),
            message=f"CIN mismatch across sources: {present}",
            rule="cin_consistency",
        )
    ]


# ---------------------------------------------------------------------------
# Rule 2 — PAN (HARD FAIL)
# Sources: PAN card, COI (post-2017 SPICe+), GSTIN[3:13], TAN letter.
# ---------------------------------------------------------------------------

def validate_pan_consistency(pans: dict[str, Optional[str]]) -> list[ValidationIssue]:
    """
    `pans`: mapping source-name → PAN. For GST_REG_06 the caller must extract
    GSTIN[3:13] before passing it in (or use ``derive_pan_from_gstin``).
    """
    present = _present(pans)
    if len(present) < 2:
        return []
    if _all_equal(present.values()):
        return []
    return [
        ValidationIssue(
            severity=Severity.HARD_FAIL,
            field="pan",
            sources=sorted(present.keys()),
            message=f"PAN mismatch across sources: {present}",
            rule="pan_consistency",
        )
    ]


def derive_pan_from_gstin(gstin: str) -> Optional[str]:
    """Per report identifier table: GSTIN positions 3-12 are the PAN of the entity."""
    parts = parse_gstin(gstin)
    return parts.pan if parts else None


# ---------------------------------------------------------------------------
# Rule 3 — Legal name (SOFT WARN, case/spacing tolerance)
# Sources: COI, MoA Name Clause, PAN card, GST REG-06 "Legal Name", Udyam, MCA Master Data.
# ---------------------------------------------------------------------------

def validate_legal_name_consistency(names: dict[str, Optional[str]]) -> list[ValidationIssue]:
    present = _present(names)
    if len(present) < 2:
        return []
    normalised = {s: _normalise_name(v) for s, v in present.items()}
    if _all_equal(normalised.values()):
        return []
    return [
        ValidationIssue(
            severity=Severity.SOFT_WARN,
            field="legal_name",
            sources=sorted(present.keys()),
            message=f"Legal name differs across sources (case/spacing tolerated): {present}",
            rule="legal_name_consistency",
        )
    ]


# ---------------------------------------------------------------------------
# Rule 4 — Date of Incorporation (HARD FAIL if year mismatches CIN)
# Sources: COI, MCA Master Data, CIN positions 9-12 (year).
# ---------------------------------------------------------------------------

def validate_doi_against_cin_year(
    cin: Optional[str],
    dois: dict[str, Optional[str]],
) -> list[ValidationIssue]:
    """
    `dois`: mapping source-name → ISO date string ("YYYY-MM-DD") or None.
    Hard-fail when any source's year differs from CIN positions 9-12.
    Soft-warn (returned via _doi_internal_consistency) is left to caller; this
    function only encodes the report's hard-fail rule.
    """
    if not cin:
        return []
    parts = parse_cin(cin)
    if not parts:
        return []
    cin_year = parts.year
    issues: list[ValidationIssue] = []
    for source, value in dois.items():
        if not value:
            continue
        try:
            year = int(str(value)[:4])
        except ValueError:
            continue
        if year != cin_year:
            issues.append(
                ValidationIssue(
                    severity=Severity.HARD_FAIL,
                    field="date_of_incorporation",
                    sources=[source, "CIN(year)"],
                    expected=str(cin_year),
                    actual=str(year),
                    message=(
                        f"Year of incorporation in {source} ({year}) "
                        f"does not match CIN positions 9-12 ({cin_year})"
                    ),
                    rule="doi_vs_cin_year",
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Rule 5 — Registered office address (SOFT WARN)
# Sources: MoA (state only), MCA Master Data (full), GST REG-06 ("Principal
# Place of Business"), recent filings.
# ---------------------------------------------------------------------------

def validate_registered_office_consistency(
    addresses: dict[str, Optional[str]],
) -> list[ValidationIssue]:
    """
    Soft-warn only. Address strings are notoriously messy across sources; we
    flag mismatches but never fail. The Stage 2 extractors should pass in
    addresses already trimmed; here we only check non-empty inequality.
    """
    present = _present(addresses)
    if len(present) < 2:
        return []
    normalised = {s: _normalise_name(v) for s, v in present.items()}
    if _all_equal(normalised.values()):
        return []
    return [
        ValidationIssue(
            severity=Severity.SOFT_WARN,
            field="registered_office_address",
            sources=sorted(present.keys()),
            message=f"Registered office address differs across sources: {present}",
            rule="registered_office_consistency",
        )
    ]


# ---------------------------------------------------------------------------
# Rule 6 — Directors list (RECONCILE BY DIN)
# Sources: DIR-12 history, DIR-3 KYC, MCA Master Data signatories.
# ---------------------------------------------------------------------------

def reconcile_directors_by_din(
    director_lists: dict[str, list[str]],
) -> list[ValidationIssue]:
    """
    `director_lists`: mapping source-name → list of DIN strings present in that source.
    The report says 'reconcile by DIN' — we surface DINs that appear in some
    sources but not others as soft warnings (since DIR-12 is event-based and
    DIR-3 KYC is per-individual; mismatches may be legitimate timing gaps).
    """
    sources = list(director_lists.keys())
    if len(sources) < 2:
        return []
    union: set[str] = set()
    for dl in director_lists.values():
        union.update(d for d in dl if d)
    issues: list[ValidationIssue] = []
    for din in sorted(union):
        present_in = [s for s, dl in director_lists.items() if din in dl]
        absent_in = [s for s in sources if s not in present_in]
        if absent_in:
            issues.append(
                ValidationIssue(
                    severity=Severity.SOFT_WARN,
                    field="directors_list",
                    sources=sorted(present_in + absent_in),
                    message=f"DIN {din} present in {present_in} but absent in {absent_in}",
                    rule="directors_reconcile_by_din",
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Rule 7 — Auditor (RECONCILE BY FRN / MEMBERSHIP)
# Sources: ADT-1, AOC-4 cross-ref, ADT-3 history.
# ---------------------------------------------------------------------------

def reconcile_auditors_by_frn_or_membership(
    auditor_keys: dict[str, list[str]],
) -> list[ValidationIssue]:
    """
    `auditor_keys`: mapping source-name → list of FRN-or-Membership strings
    that source attests to. Reconcile the union; surface deltas as soft warns
    so the user can investigate (e.g., AOC-4 still shows old auditor while
    ADT-3 has been filed for that auditor).
    """
    sources = list(auditor_keys.keys())
    if len(sources) < 2:
        return []
    union: set[str] = set()
    for keys in auditor_keys.values():
        union.update(k for k in keys if k)
    issues: list[ValidationIssue] = []
    for key in sorted(union):
        present_in = [s for s, ks in auditor_keys.items() if key in ks]
        absent_in = [s for s in sources if s not in present_in]
        if absent_in:
            issues.append(
                ValidationIssue(
                    severity=Severity.SOFT_WARN,
                    field="auditor",
                    sources=sorted(present_in + absent_in),
                    message=(
                        f"Auditor {key} present in {present_in} but absent in {absent_in}"
                    ),
                    rule="auditor_reconcile_by_frn_or_membership",
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Rule 8 — Authorised & paid-up capital (SOFT WARN)
# Sources: MoA Capital Clause, MCA Master Data, latest MGT-7.
# ---------------------------------------------------------------------------

def validate_capital_consistency(
    capitals: dict[str, dict[str, Optional[str]]],
) -> list[ValidationIssue]:
    """
    `capitals`: mapping source-name → {'authorised': str|None, 'paid_up': str|None}.
    Soft-warn on numeric inequality after stripping commas / currency symbols.
    """
    issues: list[ValidationIssue] = []
    for kind in ("authorised", "paid_up"):
        present: dict[str, str] = {}
        for source, vals in capitals.items():
            v = vals.get(kind) if isinstance(vals, dict) else None
            if v in (None, ""):
                continue
            digits = _strip_currency(str(v))
            if digits is not None:
                present[source] = digits
        if len(present) < 2:
            continue
        if _all_equal(present.values()):
            continue
        issues.append(
            ValidationIssue(
                severity=Severity.SOFT_WARN,
                field=f"{kind}_capital",
                sources=sorted(present.keys()),
                message=f"{kind.capitalize()} capital differs across sources: {present}",
                rule="capital_consistency",
            )
        )
    return issues


def _strip_currency(value: str) -> Optional[str]:
    cleaned = value.strip().replace("₹", "").replace("Rs.", "").replace("Rs", "")
    cleaned = cleaned.replace(",", "").replace(" ", "")
    if not cleaned:
        return None
    # Drop trailing decimals if zero (so "100000.00" == "100000").
    try:
        f = float(cleaned)
        return str(int(f)) if f.is_integer() else str(f)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# One-shot orchestrator
# ---------------------------------------------------------------------------

@dataclass
class CrossDocInputs:
    """Accumulator the Stage 2/3 extractors fill before calling the orchestrator."""
    cins: dict[str, Optional[str]] = field(default_factory=dict)
    pans: dict[str, Optional[str]] = field(default_factory=dict)
    legal_names: dict[str, Optional[str]] = field(default_factory=dict)
    dates_of_incorporation: dict[str, Optional[str]] = field(default_factory=dict)
    registered_offices: dict[str, Optional[str]] = field(default_factory=dict)
    director_lists: dict[str, list[str]] = field(default_factory=dict)
    auditor_keys: dict[str, list[str]] = field(default_factory=dict)
    capitals: dict[str, dict[str, Optional[str]]] = field(default_factory=dict)

    def add_pan_from_gstin(self, source: str, gstin: str) -> None:
        derived = derive_pan_from_gstin(gstin)
        if derived:
            self.pans[source] = derived


def validate_company_record(inputs: CrossDocInputs) -> list[ValidationIssue]:
    """
    Run the full report matrix against the accumulated inputs and return every
    issue found. Caller decides what to do with HARD_FAIL vs SOFT_WARN.
    """
    issues: list[ValidationIssue] = []
    issues.extend(validate_cin_consistency(inputs.cins))
    issues.extend(validate_pan_consistency(inputs.pans))
    issues.extend(validate_legal_name_consistency(inputs.legal_names))
    # The CIN that wins is whichever non-empty value is consistent across sources.
    canonical_cin = next((v for v in inputs.cins.values() if v), None)
    issues.extend(validate_doi_against_cin_year(canonical_cin, inputs.dates_of_incorporation))
    issues.extend(validate_registered_office_consistency(inputs.registered_offices))
    issues.extend(reconcile_directors_by_din(inputs.director_lists))
    issues.extend(reconcile_auditors_by_frn_or_membership(inputs.auditor_keys))
    issues.extend(validate_capital_consistency(inputs.capitals))
    return issues


def has_hard_fail(issues: Iterable[ValidationIssue]) -> bool:
    return any(i.severity == Severity.HARD_FAIL for i in issues)
