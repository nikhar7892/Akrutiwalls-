# Akrutiwalls — Document Parser

## Source of truth

All parser regexes, field names, table layouts, enums and validation rules
come from the project report **"Parser Specification — Indian Company &
Statutory Documents"** (research date 14 May 2026). **The report is the
single source of truth.** Do not invent fields, "improve" the schema, or
apply general knowledge of Indian company law that isn't in the report.
Any change to a parser regex, field, table, enum or validation rule must
come with a corresponding update to the report.

## Stage 1 — Foundation

### Document types covered (15)

Group A — identity / master:
1. Certificate of Incorporation (Form INC-11)
2. PAN Card (Company)
3. TAN Allotment Letter
4. Articles of Association (eAoA INC-34 / printed)
5. Memorandum of Association (eMoA INC-33 / printed)
6. GST Registration Certificate (Form GST REG-06)
7. MSME / Udyam Registration Certificate
8. MCA Master Data (printout from MCA21 V3)

Group B — MCA statutory filing forms:
9. DIR-12 (Appointment of Directors / KMP)
10. MGT-14 (Filing of Resolutions and Agreements)
11. ADT-1 (Auditor Appointment)
12. ADT-3 (Auditor Resignation)
13. DIR-3 KYC (KYC of Directors)
14. SRN Challan (MCA Payment Challan)
15. DPT-3 (Return of Deposits)

### Normalised schema (7 Stage-1 tables)

Physical name (`parser_*` prefix to avoid collision with existing app
tables — logical name in parentheses):

- `parser_company` (`company`) — PK = `cin`
- `parser_directors_kmp` (`directors_kmp`) — PK = `(cin, din_or_pan)`
- `parser_auditors` (`auditors`) — PK = `(cin, frn_or_membership_no, period_from)`
- `parser_resolutions_agreements` (`resolutions_agreements`) — PK = `(cin, mgt14_srn, sequence)`
- `parser_deposits` (`deposits`) — PK = `(cin, financial_year)`
- `parser_registrations` (`registrations`) — PK = `(cin, type, identifier)`; one row per GSTIN-per-State, one per Udyam, one per IEC
- `parser_mca_filings` (`mca_filings`) — PK = `srn`; the universal FK every MCA filing links through

SRN is indexed on `parser_auditors.adt1_srn`, `parser_auditors.adt3_srn`,
`parser_resolutions_agreements.mgt14_srn`, `parser_deposits.dpt3_srn`.

### Identifier formats (canonical reference)

Verbatim from the report's identifier table. Enforced in three places:
the Python validator (`parser/identifiers.py`), the Python tests
(`tests/test_identifiers.py`), and Postgres CHECK constraints in the
parser_spec_schema migration.

| ID | Length | Regex |
|---|---|---|
| CIN | 21 | `^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$` |
| LLPIN | 7 alphanumeric | `^[A-Z]{3}-?[0-9]{4}$` (TODO: confirm with sample) |
| FCRN | 6 alphanumeric | `^F[0-9]{5}$` (TODO: confirm with sample) |
| PAN | 10 | `^[A-Z]{5}[0-9]{4}[A-Z]$` |
| TAN | 10 | `^[A-Z]{4}[0-9]{5}[A-Z]$` |
| GSTIN | 15 | `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$` + Luhn-mod-36 check |
| DIN/DPIN | 8 | `^[0-9]{8}$` |
| SRN | 9 | `^[A-Z][0-9]{8}$` |
| Udyam URN | 19 (with hyphens) | `^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$` |
| IEC | 10 (= entity's PAN) | `^[A-Z]{5}[0-9]{4}[A-Z]$` |

Cross-document validation matrix is encoded in `parser/validation.py`
(8 rules: 3 hard-fail, 3 soft-warn, 2 reconcile-by-key). HARD_FAIL stops
the merge into the master; SOFT_WARN surfaces in the inconsistencies
inbox but allows the row to land.

## Stage 2 — Classifier + Group A Extractors

### Classifier — title-anchor table

`parser/classifier.py` returns the doc type for any of the 15 PDFs above.
Each anchor is verbatim from the relevant report section; rules are
priority-ordered so the most specific signal wins.

| Doc | Verbatim anchor (per report §) |
|---|---|
| COI                | "Certificate of Incorporation [Pursuant to sub-section (2) of section 7 of the Companies Act, 2013 …" (§1) |
| GST_REG_06         | "Form GST REG-06" (§6) |
| MCA_MASTER_DATA    | "Company/LLP Master Data" (§8) |
| UDYAM              | "Udyam Registration Certificate" + URN (§7) |
| MOA                | "MEMORANDUM OF ASSOCIATION OF" (§5) |
| AOA                | "ARTICLES OF ASSOCIATION OF" (§4) |
| TAN_LETTER         | "Tax Deduction Account Number" + TAN format (§3) |
| PAN_CARD           | "INCOME TAX DEPARTMENT" + "Permanent Account Number" + PAN-with-4th=C (§2) |
| SRN_CHALLAN        | "Service Description" + MoCA header + SRN (§14) |
| DIR_12             | "Form DIR-12" (§9) |
| DIR_3_KYC          | "Form DIR-3 KYC" (§13) |
| MGT_14             | "Form MGT-14" (§10) |
| ADT_1              | "Form ADT-1" (§11) |
| ADT_3              | "Form ADT-3" (§12) |
| DPT_3              | "Form DPT-3" (§15) |

V2-vs-V3 portal-version detection (report 'MCA V3 PDF Specifics — Parsing
Notes' §8) uses text-marker proxies per Group B form (visual blue-band
detection isn't possible from the text layer). Group A extractors don't
need portal-version routing.

### Group A extractors — module → target tables

| Doc | Module | Target tables |
|---|---|---|
| COI                | `parser/extractors/coi.py`               | `parser_company` |
| PAN_CARD           | `parser/extractors/pan_card.py`          | `parser_company` |
| TAN_LETTER         | `parser/extractors/tan_letter.py`        | `parser_company` |
| AOA                | `parser/extractors/aoa.py`               | `parser_company`, `parser_aoa_clauses` |
| MOA                | `parser/extractors/moa.py`               | `parser_company`, `parser_moa_clauses` |
| GST_REG_06         | `parser/extractors/gst_reg_06.py`        | `parser_company`, `parser_registrations` |
| UDYAM              | `parser/extractors/udyam.py`             | `parser_company`, `parser_registrations` |
| MCA_MASTER_DATA    | `parser/extractors/mca_master_data.py`   | `parser_company`, `parser_directors_kmp` |

Each extractor exports a single `extract(pdf_path) -> dict` returning a
chunked payload keyed by target table; the persistence layer
(`parser/persistence.py`) walks those keys.

### New tables (Stage 2)

- `parser_moa_clauses` — `(cin, clause_roman)` PK; six Roman-numeral clauses
  per MoA. `sub_clauses` JSONB carries (a) Objects' Main/Ancillary/Other
  split for clause III, (b) capital share-count + face-value + share-class
  for clause V, (c) parsed subscriber rows for clause VI.
- `parser_aoa_clauses` — `(cin, article_no, article_title, clause_no)` PK;
  one row per Table-F-style article. Sub-clauses stay raw in `clause_text`
  (the report says do NOT atomise).
- `parser_inconsistencies` — `id, cin, severity, rule, source_doc_type,
  source_doc_id, field, expected, found, created_at`. Every cross-doc
  validator outcome lands here on persist.

### Persistence rules

`persist(extracted, source_doc_type, source_doc_id?, target_cin?)`:

1. Resolve CIN: incoming chunk's CIN > caller's `target_cin` hint > lookup
   by PAN against existing master. (`target_cin` is used by docs that don't
   carry a CIN — MoA / AoA — when they're uploaded inside a known
   company workspace.)
2. Build `CrossDocInputs` from existing master + new extract, run the
   Stage 1 `validate_company_record` orchestrator.
3. Any HARD_FAIL → reject (no rows written), log issues, return
   `accepted=False`.
4. Else → upsert `parser_company` (additive merge — never overwrite an
   existing non-null value), insert child rows for any non-empty list in
   the extracted payload (`moa_clauses`, `aoa_clauses`, `registrations`,
   `directors_kmp`).
5. SOFT_WARN issues are logged to `parser_inconsistencies` but do not
   block the write.

### How Stage 3 (Group B extractors) plugs in

Stage 3 builds extractors for DIR-12, MGT-14, ADT-1, ADT-3, DIR-3 KYC,
SRN Challan and DPT-3. The classifier already routes these correctly;
Stage 3 only needs to:

1. Add a module under `parser/extractors/` per doc.
2. Register the doc-type → module mapping in
   `parser/extractors/__init__.py:_GROUP_A_MODULES` (rename to
   `_DOC_MODULES` if preferred).
3. Hand the chunked output dict to `persist()` — no changes to the
   classifier, validator, schema or persistence loop required.

### How to extend safely

- **Add a new identifier:** update the report's identifier table FIRST,
  then add the regex to `parser/identifiers.py`, the test to
  `tests/test_identifiers.py`, and the CHECK constraint to a new migration.
- **Add a new column to a parser_ table:** update the report's
  Consolidated Master Schema FIRST, then run `prisma migrate dev`. Never
  add a column the report doesn't declare.
- **Add a new validation rule:** update the report's Cross-Document
  Validation Matrix FIRST, then add the function to `parser/validation.py`
  and a test to `tests/test_validation.py`.
- **Add a new doc type:** update the report's per-document section FIRST,
  then add a classifier rule + extractor module + test.
