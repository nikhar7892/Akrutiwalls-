"""
Persistence layer for Stage 2 and Stage 3 extractor outputs.

Stage 2 (Group A) behaviour:
  - Take an extracted dict from any of the 8 Group A extractors.
  - Run the Stage 1 cross-doc validators against any existing record for the
    same CIN.
  - HARD_FAIL → reject (do not write); log to ``parser_inconsistencies`` and
    surface to caller.
  - SOFT_WARN → write the row(s); log SOFT_WARN entries.

Stage 3 (Group B) addition (S3-R1, SRN-first contract):
  - If the extracted payload has an ``mca_filing`` chunk, the doc is a Group B
    filing.  Its SRN is treated as a HARD pre-condition for any child write —
    we validate the SRN format (``^[A-Z][0-9]{8}$``) and upsert the
    ``parser_mca_filings`` row FIRST, before any ``parser_resolutions_agreements``,
    ``parser_auditors``, ``parser_deposits`` or ``parser_directors_kmp`` write.
    Missing or malformed SRN → HARD_FAIL, abort, log inconsistency.

Tables written are the Stage 1 ``parser_*`` set + the Stage 2 additions
(``parser_moa_clauses``, ``parser_aoa_clauses``, ``parser_inconsistencies``).
No new tables introduced in Stage 3 — every Group B target table already
exists in the Stage 1 schema.

This module talks to Postgres via psycopg 3, reading ``DATABASE_URL`` from
the environment (same source the existing Prisma client uses).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Optional

import psycopg
from psycopg.rows import dict_row

from parser.identifiers import is_valid_cin, is_valid_srn
from parser.validation import (
    CrossDocInputs,
    Severity,
    ValidationIssue,
    derive_pan_from_gstin,
    has_hard_fail,
    validate_company_record,
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class PersistResult:
    accepted: bool
    cin: Optional[str]
    issues: list[ValidationIssue] = field(default_factory=list)
    rows_written: dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set; persistence layer requires Postgres URL")
    # psycopg accepts the postgresql:// URL format Prisma uses; strip the
    # ?schema=public query the Prisma URL appends (psycopg uses search_path).
    url = re.sub(r"\?schema=public$", "", url)
    return psycopg.connect(url, row_factory=dict_row)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def persist(
    extracted: dict,
    source_doc_type: str,
    source_doc_id: Optional[str] = None,
    target_cin: Optional[str] = None,
) -> PersistResult:
    """
    Persist an extractor's chunked dict to the parser_* tables.

    The cross-doc validator runs FIRST. HARD_FAIL means we don't write the
    company chunk or any child rows; instead we log the issues to
    parser_inconsistencies and return accepted=False. SOFT_WARN issues are
    logged but persistence proceeds.

    `target_cin` is an explicit hint used when the caller knows which
    company this doc belongs to (e.g., MoA/AoA uploaded inside a known
    company workspace). When set and the doc itself has no CIN, this CIN is
    used as the persistence target.
    """
    company_chunk = extracted.get("company") or {}
    incoming_cin = company_chunk.get("cin") if isinstance(company_chunk, dict) else None
    mca_filing_chunk = extracted.get("mca_filing")
    is_group_b = isinstance(mca_filing_chunk, dict)
    srn = (mca_filing_chunk or {}).get("srn") if is_group_b else None

    # Resolve target CIN — incoming wins if set; else look up by other identifiers
    # (PAN match) so docs without a CIN (PAN card, TAN letter, GST cert) can land
    # against an existing master. `target_cin` is the explicit caller hint.
    with _connect() as conn:
        with conn.cursor() as cur:
            # S3-R1 pre-check: every Group B doc MUST carry a valid SRN. If not,
            # no child rows can be written; log HARD_FAIL and abort.
            if is_group_b and (not srn or not is_valid_srn(srn)):
                bad_issue = ValidationIssue(
                    severity=Severity.HARD_FAIL,
                    field="mca_filing.srn",
                    sources=[source_doc_type],
                    message=(f"Group B doc {source_doc_type} missing/invalid SRN "
                             f"(expected ^[A-Z][0-9]{{8}}$, got {srn!r})"),
                    expected="^[A-Z][0-9]{8}$",
                    actual=str(srn) if srn else None,
                    rule="srn_required_for_mca_filing",
                )
                _log_inconsistencies(cur, incoming_cin or target_cin, source_doc_type,
                                     source_doc_id, [bad_issue])
                conn.commit()
                return PersistResult(
                    accepted=False,
                    cin=incoming_cin or target_cin,
                    issues=[bad_issue],
                    error="Group B SRN missing or malformed — no rows written (S3-R1)",
                )

            existing = _resolve_existing_master(cur, incoming_cin or target_cin, company_chunk)
            existing_cin = existing["cin"] if existing else (incoming_cin or target_cin)

            # Build CrossDocInputs.
            inputs = _build_validation_inputs(existing, company_chunk, source_doc_type, extracted)
            issues = validate_company_record(inputs)

            if has_hard_fail(issues):
                _log_inconsistencies(cur, existing_cin, source_doc_type, source_doc_id, issues)
                conn.commit()
                return PersistResult(
                    accepted=False,
                    cin=existing_cin,
                    issues=issues,
                    error="cross-doc validation HARD_FAIL — extract not persisted",
                )

            # No HARD_FAIL → write the company row (upsert) and child rows.
            target_cin = existing_cin
            rows_written: dict[str, int] = {}

            # If the incoming chunk has a CIN OR an existing row found OR the
            # caller provided target_cin, we upsert the company row and write
            # children. Without any of these we have no CIN to write under.
            resolved_cin = existing_cin
            if company_chunk.get("cin") or existing_cin:
                # Upsert: caller-hint CIN may be needed if company_chunk has no cin.
                merge_chunk = dict(company_chunk)
                if not merge_chunk.get("cin") and existing_cin:
                    merge_chunk["cin"] = existing_cin
                resolved_cin = _upsert_company(cur, existing, merge_chunk)
                rows_written["parser_company"] = 1

            # S3-R1: Group B SRN-FIRST. parser_mca_filings is written BEFORE any
            # child row references it (FK invariant).
            extra_issues: list[ValidationIssue] = []
            if is_group_b and resolved_cin:
                rows_written["parser_mca_filings"] = _upsert_mca_filing(cur, resolved_cin, mca_filing_chunk)

            if resolved_cin:
                rows_written["parser_moa_clauses"] = _insert_moa_clauses(cur, resolved_cin, extracted.get("moa_clauses") or [])
                rows_written["parser_aoa_clauses"] = _insert_aoa_clauses(cur, resolved_cin, extracted.get("aoa_clauses") or [])
                rows_written["parser_registrations"] = _insert_registrations(cur, resolved_cin, extracted.get("registrations") or [])
                rows_written["parser_directors_kmp"] = _insert_directors_kmp(cur, resolved_cin, extracted.get("directors_kmp") or [])
                # Stage 3 Group B child writes
                if extracted.get("resolutions"):
                    rows_written["parser_resolutions_agreements"] = _insert_resolutions(
                        cur, resolved_cin, srn, extracted["resolutions"],
                    )
                if extracted.get("auditors"):
                    auditor_rows, auditor_issues = _insert_or_update_auditors(
                        cur, resolved_cin, srn, source_doc_type, extracted["auditors"],
                    )
                    rows_written["parser_auditors"] = auditor_rows
                    extra_issues.extend(auditor_issues)
                if extracted.get("deposits"):
                    rows_written["parser_deposits"] = _insert_deposits(
                        cur, resolved_cin, srn, extracted["deposits"],
                    )
                # DIR-3 KYC updates an existing director row by DIN — handled in
                # the directors_kmp writer when the chunk carries KYC fields.

            all_issues = list(issues) + extra_issues
            _log_inconsistencies(cur, resolved_cin, source_doc_type, source_doc_id, all_issues)
            conn.commit()

            return PersistResult(
                accepted=True,
                cin=resolved_cin,
                issues=all_issues,
                rows_written={k: v for k, v in rows_written.items() if v},
            )


# ---------------------------------------------------------------------------
# Lookup + validation prep
# ---------------------------------------------------------------------------

def _resolve_existing_master(cur, incoming_cin: Optional[str], company_chunk: dict) -> Optional[dict]:
    if incoming_cin and is_valid_cin(incoming_cin):
        cur.execute("SELECT * FROM parser_company WHERE cin = %s", (incoming_cin,))
        row = cur.fetchone()
        if row:
            return row
    # Try PAN — docs without CIN can still land if PAN matches an existing row.
    pan = company_chunk.get("pan")
    if pan:
        cur.execute("SELECT * FROM parser_company WHERE pan = %s LIMIT 1", (pan,))
        row = cur.fetchone()
        if row:
            return row
    return None


def _build_validation_inputs(
    existing: Optional[dict],
    company_chunk: dict,
    source_doc_type: str,
    extracted: dict,
) -> CrossDocInputs:
    inputs = CrossDocInputs()
    if existing:
        if existing.get("cin"):
            inputs.cins["EXISTING_MASTER"] = existing["cin"]
        if existing.get("pan"):
            inputs.pans["EXISTING_MASTER"] = existing["pan"]
        if existing.get("legal_name"):
            inputs.legal_names["EXISTING_MASTER"] = existing["legal_name"]
        doi = existing.get("date_of_incorporation")
        if doi:
            inputs.dates_of_incorporation["EXISTING_MASTER"] = _iso(doi)
        if existing.get("registered_office_address"):
            inputs.registered_offices["EXISTING_MASTER"] = existing["registered_office_address"]
        if existing.get("authorised_capital") is not None or existing.get("paid_up_capital") is not None:
            inputs.capitals["EXISTING_MASTER"] = {
                "authorised": str(existing["authorised_capital"]) if existing.get("authorised_capital") is not None else None,
                "paid_up": str(existing["paid_up_capital"]) if existing.get("paid_up_capital") is not None else None,
            }

    if company_chunk.get("cin"):
        inputs.cins[source_doc_type] = company_chunk["cin"]
    if company_chunk.get("pan"):
        inputs.pans[source_doc_type] = company_chunk["pan"]
    if company_chunk.get("legal_name"):
        inputs.legal_names[source_doc_type] = company_chunk["legal_name"]
    if company_chunk.get("date_of_incorporation"):
        inputs.dates_of_incorporation[source_doc_type] = _iso(company_chunk["date_of_incorporation"])
    if company_chunk.get("registered_office_address"):
        inputs.registered_offices[source_doc_type] = company_chunk["registered_office_address"]
    if company_chunk.get("authorised_capital") is not None or company_chunk.get("paid_up_capital") is not None:
        inputs.capitals[source_doc_type] = {
            "authorised": str(company_chunk["authorised_capital"]) if company_chunk.get("authorised_capital") is not None else None,
            "paid_up": str(company_chunk["paid_up_capital"]) if company_chunk.get("paid_up_capital") is not None else None,
        }

    # GST certificate adds a derived PAN per the report's identifier-table rule.
    for reg in extracted.get("registrations") or []:
        if reg.get("type") == "GST" and reg.get("gstin"):
            derived = derive_pan_from_gstin(reg["gstin"])
            if derived:
                inputs.pans[source_doc_type + ":GSTIN"] = derived

    # Directors lists per Rule 6 (reconcile by DIN).
    directors = extracted.get("directors_kmp") or []
    if directors:
        dlist = [d.get("din") for d in directors if d.get("din")]
        if dlist:
            inputs.director_lists[source_doc_type] = dlist
    return inputs


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

# parser_company columns the writer is allowed to touch (Stage 1 schema).
_COMPANY_WRITE_COLUMNS = (
    "cin", "pan", "tan", "legal_name", "former_names", "date_of_incorporation",
    "roc_jurisdiction", "company_category", "company_sub_category", "listing_status",
    "company_status", "registered_office_address", "registered_office_email",
    "authorised_capital", "paid_up_capital", "nic_industry_code",
    "industrial_activity_description", "last_agm_date", "last_balance_sheet_date",
    "cin_history",
)


def _upsert_company(cur, existing: Optional[dict], company_chunk: dict) -> str:
    """
    Insert or update parser_company. Strategy: keep existing non-null values,
    only fill in fields the new extract provides where the existing master
    is empty. This makes the master additive across documents — the
    cross-doc validator already prevented contradictions.
    """
    merged: dict[str, Any] = {}
    if existing:
        for k in _COMPANY_WRITE_COLUMNS:
            if k in existing and existing[k] is not None:
                merged[k] = existing[k]
    for k, v in company_chunk.items():
        if k not in _COMPANY_WRITE_COLUMNS:
            continue
        if v in (None, "", []):
            continue
        # Don't overwrite an existing value — additive merge only.
        if merged.get(k) is None:
            merged[k] = v
    if "cin" not in merged or not merged["cin"]:
        # Required PK; cannot upsert without it.
        raise RuntimeError("Cannot upsert parser_company without a CIN")
    # Coerce dates from ISO strings.
    for date_col in ("date_of_incorporation", "last_agm_date", "last_balance_sheet_date"):
        if isinstance(merged.get(date_col), str):
            merged[date_col] = _coerce_date(merged[date_col])

    columns = list(merged.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    update_assignments = ", ".join([f"{c} = EXCLUDED.{c}" for c in columns if c != "cin"])

    sql = f"""
        INSERT INTO parser_company ({", ".join(columns)}, updated_at)
        VALUES ({placeholders}, NOW())
        ON CONFLICT (cin) DO UPDATE SET
            {update_assignments},
            updated_at = NOW()
    """
    cur.execute(sql, [merged[c] for c in columns])
    return merged["cin"]


def _insert_moa_clauses(cur, cin: str, clauses: list[dict]) -> int:
    if not clauses:
        return 0
    n = 0
    for c in clauses:
        if not c.get("clause_roman") or not c.get("clause_title"):
            continue
        sub = c.get("sub_clauses")
        cur.execute(
            """
            INSERT INTO parser_moa_clauses
                (cin, clause_roman, clause_title, clause_text, sub_clauses, updated_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT (cin, clause_roman) DO UPDATE SET
                clause_title = EXCLUDED.clause_title,
                clause_text  = EXCLUDED.clause_text,
                sub_clauses  = EXCLUDED.sub_clauses,
                updated_at   = NOW()
            """,
            (cin, c["clause_roman"], c["clause_title"], c.get("clause_text") or "",
             _json_dumps(sub) if sub is not None else None),
        )
        n += 1
    return n


def _insert_aoa_clauses(cur, cin: str, clauses: list[dict]) -> int:
    if not clauses:
        return 0
    n = 0
    for c in clauses:
        if not c.get("article_no") or not c.get("article_title"):
            continue
        clause_no = str(c.get("clause_no") or "0")
        cur.execute(
            """
            INSERT INTO parser_aoa_clauses
                (cin, article_no, article_title, clause_no, clause_text, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (cin, article_no, article_title, clause_no) DO UPDATE SET
                clause_text = EXCLUDED.clause_text,
                updated_at  = NOW()
            """,
            (cin, c["article_no"], c["article_title"], clause_no, c.get("clause_text") or ""),
        )
        n += 1
    return n


def _insert_registrations(cur, cin: str, regs: list[dict]) -> int:
    if not regs:
        return 0
    n = 0
    for r in regs:
        rtype = r.get("type")
        identifier = r.get("identifier")
        if not rtype or not identifier:
            continue
        cols = [
            "cin", "type", "identifier", "gstin", "gst_legal_name", "gst_trade_name",
            "constitution_of_business", "principal_place_of_business",
            "additional_places_of_business",
            "date_of_liability", "period_of_validity_from", "period_of_validity_to",
            "type_of_registration",
            "udyam_registration_number", "udyam_enterprise_type",
            "udyam_date_of_registration", "udyam_date_of_commencement", "nic_codes",
        ]
        values: list[Any] = []
        for col in cols:
            v = r.get(col)
            if col in ("date_of_liability", "period_of_validity_from", "period_of_validity_to",
                       "udyam_date_of_registration", "udyam_date_of_commencement") and isinstance(v, str):
                v = _coerce_date(v)
            if col == "additional_places_of_business":
                v = list(v) if v else []
            if col == "nic_codes":
                v = list(v) if v else []
            if col == "cin":
                v = cin
            if col == "type":
                v = rtype
            if col == "identifier":
                v = identifier
            values.append(v)
        placeholders = ", ".join(["%s"] * len(cols))
        update_assignments = ", ".join([f"{c} = EXCLUDED.{c}" for c in cols if c not in ("cin", "type", "identifier")])
        cur.execute(
            f"""
            INSERT INTO parser_registrations ({", ".join(cols)}, updated_at)
            VALUES ({placeholders}, NOW())
            ON CONFLICT (cin, type, identifier) DO UPDATE SET
                {update_assignments},
                updated_at = NOW()
            """,
            values,
        )
        n += 1
    return n


def _insert_directors_kmp(cur, cin: str, directors: list[dict]) -> int:
    if not directors:
        return 0
    n = 0
    for d in directors:
        din = d.get("din")
        pan = d.get("pan")
        din_or_pan = d.get("din_or_pan") or din or pan
        if not din_or_pan:
            continue
        appointment = d.get("date_of_appointment")
        if isinstance(appointment, str):
            appointment = _coerce_date(appointment)
        cessation = d.get("date_of_cessation")
        if isinstance(cessation, str):
            cessation = _coerce_date(cessation)
        # Stage 3: DIR-3 KYC fields. Optional in the extractor payload.
        dob = d.get("dob")
        if isinstance(dob, str):
            dob = _coerce_date(dob)
        kyc_last_filed = d.get("kyc_last_filed_date")
        if isinstance(kyc_last_filed, str):
            kyc_last_filed = _coerce_date(kyc_last_filed)
        kyc_due = d.get("kyc_due_date")
        if isinstance(kyc_due, str):
            kyc_due = _coerce_date(kyc_due)
        cur.execute(
            """
            INSERT INTO parser_directors_kmp
                (cin, din_or_pan, din, pan, name, designation, category,
                 nationality, dob, gender, father_name,
                 address_permanent, address_present, email, mobile,
                 aadhaar_last4, passport_no,
                 kyc_last_filed_date, kyc_due_date,
                 date_of_appointment, date_of_cessation,
                 updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    NOW())
            ON CONFLICT (cin, din_or_pan) DO UPDATE SET
                name                = COALESCE(EXCLUDED.name,                parser_directors_kmp.name),
                designation         = COALESCE(EXCLUDED.designation,         parser_directors_kmp.designation),
                category            = COALESCE(EXCLUDED.category,            parser_directors_kmp.category),
                nationality         = COALESCE(EXCLUDED.nationality,         parser_directors_kmp.nationality),
                dob                 = COALESCE(EXCLUDED.dob,                 parser_directors_kmp.dob),
                gender              = COALESCE(EXCLUDED.gender,              parser_directors_kmp.gender),
                father_name         = COALESCE(EXCLUDED.father_name,         parser_directors_kmp.father_name),
                address_permanent   = COALESCE(EXCLUDED.address_permanent,   parser_directors_kmp.address_permanent),
                address_present     = COALESCE(EXCLUDED.address_present,     parser_directors_kmp.address_present),
                email               = COALESCE(EXCLUDED.email,               parser_directors_kmp.email),
                mobile              = COALESCE(EXCLUDED.mobile,              parser_directors_kmp.mobile),
                aadhaar_last4       = COALESCE(EXCLUDED.aadhaar_last4,       parser_directors_kmp.aadhaar_last4),
                passport_no         = COALESCE(EXCLUDED.passport_no,         parser_directors_kmp.passport_no),
                kyc_last_filed_date = COALESCE(EXCLUDED.kyc_last_filed_date, parser_directors_kmp.kyc_last_filed_date),
                kyc_due_date        = COALESCE(EXCLUDED.kyc_due_date,        parser_directors_kmp.kyc_due_date),
                date_of_appointment = COALESCE(EXCLUDED.date_of_appointment, parser_directors_kmp.date_of_appointment),
                date_of_cessation   = COALESCE(EXCLUDED.date_of_cessation,   parser_directors_kmp.date_of_cessation),
                updated_at          = NOW()
            """,
            (cin, din_or_pan, din, pan, d.get("name"), d.get("designation"),
             d.get("category"),
             d.get("nationality"), dob, d.get("gender"), d.get("father_name"),
             d.get("address_permanent"), d.get("address_present"),
             d.get("email"), d.get("mobile"),
             d.get("aadhaar_last4"), d.get("passport_no"),
             kyc_last_filed, kyc_due,
             appointment, cessation),
        )
        n += 1
    return n


# ---------------------------------------------------------------------------
# Stage 3 writers — parser_mca_filings, parser_resolutions_agreements,
# parser_auditors (insert + update path), parser_deposits.
# ---------------------------------------------------------------------------

# parser_mca_filings columns the writer is allowed to touch.
_MCA_FILING_COLUMNS = (
    "srn", "cin", "form_type", "purpose", "filing_date", "event_date",
    "fee_paid", "additional_fee", "payment_mode", "payment_status",
    "processing_status", "dsc_signatory", "professional_certifier",
    "attachment_list",
)


def _upsert_mca_filing(cur, cin: str, chunk: dict) -> int:
    """Write parser_mca_filings row. SRN-first per S3-R1."""
    if not chunk or not chunk.get("srn"):
        return 0
    values: dict[str, Any] = {"cin": cin}
    for col in _MCA_FILING_COLUMNS:
        if col == "cin":
            continue
        v = chunk.get(col)
        if v in (None, "", []):
            continue
        if col in ("filing_date", "event_date") and isinstance(v, str):
            v = _coerce_date(v)
        if col == "attachment_list":
            v = list(v) if v else []
        values[col] = v
    columns = list(values.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    assigns = ", ".join([f"{c} = EXCLUDED.{c}" for c in columns if c != "srn"])
    sql = f"""
        INSERT INTO parser_mca_filings ({", ".join(columns)}, updated_at)
        VALUES ({placeholders}, NOW())
        ON CONFLICT (srn) DO UPDATE SET
            {assigns},
            updated_at = NOW()
    """
    cur.execute(sql, [values[c] for c in columns])
    return 1


def _insert_resolutions(cur, cin: str, mgt14_srn: Optional[str], rows: list[dict]) -> int:
    if not mgt14_srn or not rows:
        return 0
    n = 0
    for i, r in enumerate(rows, start=1):
        seq = int(r.get("sequence") or i)
        passed = r.get("date_passed")
        if isinstance(passed, str):
            passed = _coerce_date(passed)
        mdate = r.get("meeting_date")
        if isinstance(mdate, str):
            mdate = _coerce_date(mdate)
        cur.execute(
            """
            INSERT INTO parser_resolutions_agreements
                (cin, mgt14_srn, sequence, resolution_type, section_under, purpose,
                 date_passed, meeting_type, meeting_date, attachment_pointer)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cin, mgt14_srn, sequence) DO UPDATE SET
                resolution_type    = EXCLUDED.resolution_type,
                section_under      = EXCLUDED.section_under,
                purpose            = EXCLUDED.purpose,
                date_passed        = EXCLUDED.date_passed,
                meeting_type       = EXCLUDED.meeting_type,
                meeting_date       = EXCLUDED.meeting_date,
                attachment_pointer = EXCLUDED.attachment_pointer
            """,
            (cin, mgt14_srn, seq,
             r.get("resolution_type"), r.get("section_under"), r.get("purpose"),
             passed, r.get("meeting_type"), mdate, r.get("attachment_pointer")),
        )
        n += 1
    return n


def _insert_or_update_auditors(
    cur, cin: str, srn: Optional[str], source_doc_type: str, auditors: list[dict],
) -> tuple[int, list[ValidationIssue]]:
    """
    Insert / update parser_auditors rows. ADT-1 paths insert; ADT-3 paths
    update an existing row by (cin, frn_or_membership_no) — if no matching
    row exists, persist a stub anyway and emit a SOFT_WARN per Stage 3 brief
    ("ADT-3 received before ADT-1 for this auditor/company").
    """
    issues: list[ValidationIssue] = []
    written = 0
    is_adt3 = source_doc_type == "ADT_3"

    for a in auditors:
        key = a.get("frn_or_membership_no") or a.get("firm_registration_no") or a.get("icai_membership_no")
        if not key:
            continue
        period_from = a.get("period_from")
        if isinstance(period_from, str):
            period_from = _coerce_date(period_from)
        if not period_from and is_adt3:
            # Try to find the latest period_from row for this (cin, key) and reuse.
            cur.execute(
                "SELECT period_from FROM parser_auditors WHERE cin = %s AND frn_or_membership_no = %s "
                "ORDER BY period_from DESC LIMIT 1",
                (cin, key),
            )
            row = cur.fetchone()
            if row:
                period_from = row["period_from"]
        if not period_from:
            # Last-resort fallback for ADT-3 with no matching ADT-1: use the
            # resignation_date as the period_from, stub the row, and warn.
            if is_adt3:
                resignation_date = a.get("resignation_date")
                if isinstance(resignation_date, str):
                    resignation_date = _coerce_date(resignation_date)
                if resignation_date:
                    period_from = resignation_date
            if not period_from:
                # Cannot satisfy composite PK — skip and warn.
                issues.append(ValidationIssue(
                    severity=Severity.SOFT_WARN,
                    field="auditors.period_from",
                    sources=[source_doc_type],
                    message=f"Auditor {key} missing period_from — cannot persist",
                    rule="auditor_period_from_missing",
                ))
                continue
            issues.append(ValidationIssue(
                severity=Severity.SOFT_WARN,
                field="auditors",
                sources=[source_doc_type],
                message=(f"ADT-3 received before ADT-1 for {key} (cin={cin}); "
                         "stubbing parser_auditors row from ADT-3 data."),
                rule="adt3_before_adt1",
            ))

        period_to = a.get("period_to")
        if isinstance(period_to, str):
            period_to = _coerce_date(period_to)
        date_of_appointment = a.get("date_of_appointment")
        if isinstance(date_of_appointment, str):
            date_of_appointment = _coerce_date(date_of_appointment)
        agm_date = a.get("agm_date")
        if isinstance(agm_date, str):
            agm_date = _coerce_date(agm_date)
        resignation_date = a.get("resignation_date")
        if isinstance(resignation_date, str):
            resignation_date = _coerce_date(resignation_date)

        cur.execute(
            """
            INSERT INTO parser_auditors
                (cin, frn_or_membership_no, period_from, category, name, pan,
                 icai_membership_no, firm_registration_no, address, email,
                 date_of_appointment, period_to, tenure_years, appointment_type,
                 agm_date, adt1_srn, resignation_date, resignation_reason, adt3_srn,
                 updated_at)
            VALUES (%s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    NOW())
            ON CONFLICT (cin, frn_or_membership_no, period_from) DO UPDATE SET
                category              = COALESCE(EXCLUDED.category,              parser_auditors.category),
                name                  = COALESCE(EXCLUDED.name,                  parser_auditors.name),
                pan                   = COALESCE(EXCLUDED.pan,                   parser_auditors.pan),
                icai_membership_no    = COALESCE(EXCLUDED.icai_membership_no,    parser_auditors.icai_membership_no),
                firm_registration_no  = COALESCE(EXCLUDED.firm_registration_no,  parser_auditors.firm_registration_no),
                address               = COALESCE(EXCLUDED.address,               parser_auditors.address),
                email                 = COALESCE(EXCLUDED.email,                 parser_auditors.email),
                date_of_appointment   = COALESCE(EXCLUDED.date_of_appointment,   parser_auditors.date_of_appointment),
                period_to             = COALESCE(EXCLUDED.period_to,             parser_auditors.period_to),
                tenure_years          = COALESCE(EXCLUDED.tenure_years,          parser_auditors.tenure_years),
                appointment_type      = COALESCE(EXCLUDED.appointment_type,      parser_auditors.appointment_type),
                agm_date              = COALESCE(EXCLUDED.agm_date,              parser_auditors.agm_date),
                adt1_srn              = COALESCE(EXCLUDED.adt1_srn,              parser_auditors.adt1_srn),
                resignation_date      = COALESCE(EXCLUDED.resignation_date,      parser_auditors.resignation_date),
                resignation_reason    = COALESCE(EXCLUDED.resignation_reason,    parser_auditors.resignation_reason),
                adt3_srn              = COALESCE(EXCLUDED.adt3_srn,              parser_auditors.adt3_srn),
                updated_at            = NOW()
            """,
            (cin, key, period_from,
             a.get("category"), a.get("name"), a.get("pan"),
             a.get("icai_membership_no"), a.get("firm_registration_no"),
             a.get("address"), a.get("email"),
             date_of_appointment, period_to, a.get("tenure_years"), a.get("appointment_type"),
             agm_date,
             a.get("adt1_srn") or (srn if source_doc_type == "ADT_1" else None),
             resignation_date, a.get("resignation_reason"),
             a.get("adt3_srn") or (srn if source_doc_type == "ADT_3" else None)),
        )
        written += 1
    return written, issues


def _insert_deposits(cur, cin: str, dpt3_srn: Optional[str], rows: list[dict]) -> int:
    if not rows:
        return 0
    n = 0
    for r in rows:
        fy = r.get("financial_year")
        if not fy:
            continue
        cur.execute(
            """
            INSERT INTO parser_deposits
                (cin, financial_year, purpose_of_filing,
                 outstanding_secured, outstanding_unsecured, outstanding_non_deposit,
                 net_worth, credit_rating, dpt3_srn, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (cin, financial_year) DO UPDATE SET
                purpose_of_filing       = COALESCE(EXCLUDED.purpose_of_filing,       parser_deposits.purpose_of_filing),
                outstanding_secured     = COALESCE(EXCLUDED.outstanding_secured,     parser_deposits.outstanding_secured),
                outstanding_unsecured   = COALESCE(EXCLUDED.outstanding_unsecured,   parser_deposits.outstanding_unsecured),
                outstanding_non_deposit = COALESCE(EXCLUDED.outstanding_non_deposit, parser_deposits.outstanding_non_deposit),
                net_worth               = COALESCE(EXCLUDED.net_worth,               parser_deposits.net_worth),
                credit_rating           = COALESCE(EXCLUDED.credit_rating,           parser_deposits.credit_rating),
                dpt3_srn                = COALESCE(EXCLUDED.dpt3_srn,                parser_deposits.dpt3_srn),
                updated_at              = NOW()
            """,
            (cin, fy, r.get("purpose_of_filing"),
             r.get("outstanding_secured"), r.get("outstanding_unsecured"),
             r.get("outstanding_non_deposit"), r.get("net_worth"),
             r.get("credit_rating"), r.get("dpt3_srn") or dpt3_srn),
        )
        n += 1
    return n


def _log_inconsistencies(cur, cin: Optional[str], source_doc_type: str,
                         source_doc_id: Optional[str], issues: Iterable[ValidationIssue]) -> int:
    n = 0
    for issue in issues:
        cur.execute(
            """
            INSERT INTO parser_inconsistencies
                (id, cin, severity, rule, source_doc_type, source_doc_id, field, expected, found)
            VALUES (gen_random_uuid()::text, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                cin, issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity),
                issue.rule, source_doc_type, source_doc_id, issue.field,
                issue.expected, issue.actual,
            ),
        )
        n += 1
    return n


# ---------------------------------------------------------------------------
# Coercion utilities
# ---------------------------------------------------------------------------

def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value)[:10]


def _coerce_date(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _json_dumps(obj: Any) -> str:
    import json
    def default(o: Any) -> Any:
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return str(o)
        return str(o)
    return json.dumps(obj, default=default)
