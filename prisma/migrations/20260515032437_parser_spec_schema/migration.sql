-- CreateTable
CREATE TABLE "parser_company" (
    "cin" TEXT NOT NULL,
    "pan" TEXT,
    "tan" TEXT,
    "legal_name" TEXT NOT NULL,
    "former_names" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "date_of_incorporation" DATE,
    "roc_jurisdiction" TEXT,
    "company_category" TEXT,
    "company_sub_category" TEXT,
    "listing_status" TEXT,
    "company_status" TEXT,
    "registered_office_address" TEXT,
    "registered_office_email" TEXT,
    "authorised_capital" DECIMAL(20,2),
    "paid_up_capital" DECIMAL(20,2),
    "nic_industry_code" TEXT,
    "industrial_activity_description" TEXT,
    "last_agm_date" DATE,
    "last_balance_sheet_date" DATE,
    "cin_history" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "parser_company_pkey" PRIMARY KEY ("cin")
);

-- CreateTable
CREATE TABLE "parser_directors_kmp" (
    "cin" TEXT NOT NULL,
    "din_or_pan" TEXT NOT NULL,
    "din" TEXT,
    "pan" TEXT,
    "name" TEXT,
    "designation" TEXT,
    "category" TEXT,
    "date_of_appointment" DATE,
    "date_of_cessation" DATE,
    "nationality" TEXT,
    "dob" DATE,
    "gender" TEXT,
    "father_name" TEXT,
    "address_permanent" TEXT,
    "address_present" TEXT,
    "email" TEXT,
    "mobile" TEXT,
    "aadhaar_last4" TEXT,
    "passport_no" TEXT,
    "kyc_last_filed_date" DATE,
    "kyc_due_date" DATE,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "parser_directors_kmp_pkey" PRIMARY KEY ("cin","din_or_pan")
);

-- CreateTable
CREATE TABLE "parser_auditors" (
    "cin" TEXT NOT NULL,
    "frn_or_membership_no" TEXT NOT NULL,
    "period_from" DATE NOT NULL,
    "category" TEXT,
    "name" TEXT,
    "pan" TEXT,
    "icai_membership_no" TEXT,
    "firm_registration_no" TEXT,
    "address" TEXT,
    "email" TEXT,
    "date_of_appointment" DATE,
    "period_to" DATE,
    "tenure_years" INTEGER,
    "appointment_type" TEXT,
    "agm_date" DATE,
    "adt1_srn" TEXT,
    "resignation_date" DATE,
    "resignation_reason" TEXT,
    "adt3_srn" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "parser_auditors_pkey" PRIMARY KEY ("cin","frn_or_membership_no","period_from")
);

-- CreateTable
CREATE TABLE "parser_resolutions_agreements" (
    "cin" TEXT NOT NULL,
    "mgt14_srn" TEXT NOT NULL,
    "sequence" INTEGER NOT NULL,
    "resolution_type" TEXT,
    "section_under" TEXT,
    "purpose" TEXT,
    "date_passed" DATE,
    "meeting_type" TEXT,
    "meeting_date" DATE,
    "attachment_pointer" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "parser_resolutions_agreements_pkey" PRIMARY KEY ("cin","mgt14_srn","sequence")
);

-- CreateTable
CREATE TABLE "parser_deposits" (
    "cin" TEXT NOT NULL,
    "financial_year" TEXT NOT NULL,
    "purpose_of_filing" TEXT,
    "outstanding_secured" DECIMAL(20,2),
    "outstanding_unsecured" DECIMAL(20,2),
    "outstanding_non_deposit" DECIMAL(20,2),
    "net_worth" DECIMAL(20,2),
    "credit_rating" TEXT,
    "dpt3_srn" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "parser_deposits_pkey" PRIMARY KEY ("cin","financial_year")
);

-- CreateTable
CREATE TABLE "parser_registrations" (
    "cin" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "identifier" TEXT NOT NULL,
    "gstin" TEXT,
    "gst_legal_name" TEXT,
    "gst_trade_name" TEXT,
    "constitution_of_business" TEXT,
    "principal_place_of_business" TEXT,
    "additional_places_of_business" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "date_of_liability" DATE,
    "period_of_validity_from" DATE,
    "period_of_validity_to" DATE,
    "type_of_registration" TEXT,
    "udyam_registration_number" TEXT,
    "udyam_enterprise_type" TEXT,
    "udyam_date_of_registration" DATE,
    "udyam_date_of_commencement" DATE,
    "nic_codes" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "parser_registrations_pkey" PRIMARY KEY ("cin","type","identifier")
);

-- CreateTable
CREATE TABLE "parser_mca_filings" (
    "srn" TEXT NOT NULL,
    "cin" TEXT NOT NULL,
    "form_type" TEXT NOT NULL,
    "purpose" TEXT,
    "filing_date" DATE,
    "event_date" DATE,
    "fee_paid" DECIMAL(20,2),
    "additional_fee" DECIMAL(20,2),
    "payment_mode" TEXT,
    "payment_status" TEXT,
    "processing_status" TEXT,
    "dsc_signatory" TEXT,
    "professional_certifier" TEXT,
    "attachment_list" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "parser_mca_filings_pkey" PRIMARY KEY ("srn")
);

-- CreateIndex
CREATE INDEX "parser_directors_kmp_din_idx" ON "parser_directors_kmp"("din");

-- CreateIndex
CREATE INDEX "parser_directors_kmp_pan_idx" ON "parser_directors_kmp"("pan");

-- CreateIndex
CREATE INDEX "parser_auditors_adt1_srn_idx" ON "parser_auditors"("adt1_srn");

-- CreateIndex
CREATE INDEX "parser_auditors_adt3_srn_idx" ON "parser_auditors"("adt3_srn");

-- CreateIndex
CREATE INDEX "parser_resolutions_agreements_mgt14_srn_idx" ON "parser_resolutions_agreements"("mgt14_srn");

-- CreateIndex
CREATE INDEX "parser_deposits_dpt3_srn_idx" ON "parser_deposits"("dpt3_srn");

-- CreateIndex
CREATE INDEX "parser_mca_filings_cin_idx" ON "parser_mca_filings"("cin");

-- CreateIndex
CREATE INDEX "parser_mca_filings_form_type_idx" ON "parser_mca_filings"("form_type");

-- AddForeignKey
ALTER TABLE "parser_directors_kmp" ADD CONSTRAINT "parser_directors_kmp_cin_fkey" FOREIGN KEY ("cin") REFERENCES "parser_company"("cin") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "parser_auditors" ADD CONSTRAINT "parser_auditors_cin_fkey" FOREIGN KEY ("cin") REFERENCES "parser_company"("cin") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "parser_auditors" ADD CONSTRAINT "parser_auditors_adt1_srn_fkey" FOREIGN KEY ("adt1_srn") REFERENCES "parser_mca_filings"("srn") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "parser_auditors" ADD CONSTRAINT "parser_auditors_adt3_srn_fkey" FOREIGN KEY ("adt3_srn") REFERENCES "parser_mca_filings"("srn") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "parser_resolutions_agreements" ADD CONSTRAINT "parser_resolutions_agreements_cin_fkey" FOREIGN KEY ("cin") REFERENCES "parser_company"("cin") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "parser_resolutions_agreements" ADD CONSTRAINT "parser_resolutions_agreements_mgt14_srn_fkey" FOREIGN KEY ("mgt14_srn") REFERENCES "parser_mca_filings"("srn") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "parser_deposits" ADD CONSTRAINT "parser_deposits_cin_fkey" FOREIGN KEY ("cin") REFERENCES "parser_company"("cin") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "parser_deposits" ADD CONSTRAINT "parser_deposits_dpt3_srn_fkey" FOREIGN KEY ("dpt3_srn") REFERENCES "parser_mca_filings"("srn") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "parser_registrations" ADD CONSTRAINT "parser_registrations_cin_fkey" FOREIGN KEY ("cin") REFERENCES "parser_company"("cin") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "parser_mca_filings" ADD CONSTRAINT "parser_mca_filings_cin_fkey" FOREIGN KEY ("cin") REFERENCES "parser_company"("cin") ON DELETE CASCADE ON UPDATE CASCADE;

-- ===========================================================================
-- CHECK constraints: identifier formats. Regex strings are taken verbatim from
-- the project report 'Parser Specification — Indian Company & Statutory
-- Documents', section 'Canonical Identifier Format Reference'. Do NOT modify
-- without a corresponding update to the report.
-- ===========================================================================

-- CIN: 21-char, ^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$
ALTER TABLE "parser_company"
  ADD CONSTRAINT "parser_company_cin_format_chk"
  CHECK (cin ~ '^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$');

-- PAN: 10-char, ^[A-Z]{5}[0-9]{4}[A-Z]$
ALTER TABLE "parser_company"
  ADD CONSTRAINT "parser_company_pan_format_chk"
  CHECK (pan IS NULL OR pan ~ '^[A-Z]{5}[0-9]{4}[A-Z]$');

-- TAN: 10-char, ^[A-Z]{4}[0-9]{5}[A-Z]$
ALTER TABLE "parser_company"
  ADD CONSTRAINT "parser_company_tan_format_chk"
  CHECK (tan IS NULL OR tan ~ '^[A-Z]{4}[0-9]{5}[A-Z]$');

-- DIN (when present): 8 numeric, ^[0-9]{8}$
ALTER TABLE "parser_directors_kmp"
  ADD CONSTRAINT "parser_directors_kmp_din_format_chk"
  CHECK (din IS NULL OR din ~ '^[0-9]{8}$');

-- PAN on directors_kmp (when present): same as company PAN format
ALTER TABLE "parser_directors_kmp"
  ADD CONSTRAINT "parser_directors_kmp_pan_format_chk"
  CHECK (pan IS NULL OR pan ~ '^[A-Z]{5}[0-9]{4}[A-Z]$');

-- PAN on auditors (when present)
ALTER TABLE "parser_auditors"
  ADD CONSTRAINT "parser_auditors_pan_format_chk"
  CHECK (pan IS NULL OR pan ~ '^[A-Z]{5}[0-9]{4}[A-Z]$');

-- SRN format on auditors (ADT-1, ADT-3): ^[A-Z][0-9]{8}$
ALTER TABLE "parser_auditors"
  ADD CONSTRAINT "parser_auditors_adt1_srn_format_chk"
  CHECK (adt1_srn IS NULL OR adt1_srn ~ '^[A-Z][0-9]{8}$');
ALTER TABLE "parser_auditors"
  ADD CONSTRAINT "parser_auditors_adt3_srn_format_chk"
  CHECK (adt3_srn IS NULL OR adt3_srn ~ '^[A-Z][0-9]{8}$');

-- SRN format on resolutions_agreements (MGT-14)
ALTER TABLE "parser_resolutions_agreements"
  ADD CONSTRAINT "parser_resolutions_agreements_mgt14_srn_format_chk"
  CHECK (mgt14_srn ~ '^[A-Z][0-9]{8}$');

-- SRN format on deposits (DPT-3, when present)
ALTER TABLE "parser_deposits"
  ADD CONSTRAINT "parser_deposits_dpt3_srn_format_chk"
  CHECK (dpt3_srn IS NULL OR dpt3_srn ~ '^[A-Z][0-9]{8}$');

-- SRN format on mca_filings (PK)
ALTER TABLE "parser_mca_filings"
  ADD CONSTRAINT "parser_mca_filings_srn_format_chk"
  CHECK (srn ~ '^[A-Z][0-9]{8}$');

-- GSTIN format on registrations (when present): regex only; Luhn-mod-36 check
-- is enforced in Python (parser/identifiers.py:is_valid_gstin). The report's
-- caveats §4 notes the checksum is best-known but not officially published,
-- so it is not a DB-level constraint.
ALTER TABLE "parser_registrations"
  ADD CONSTRAINT "parser_registrations_gstin_format_chk"
  CHECK (gstin IS NULL OR gstin ~ '^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$');

-- Udyam URN format on registrations (when present): ^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$
ALTER TABLE "parser_registrations"
  ADD CONSTRAINT "parser_registrations_udyam_format_chk"
  CHECK (udyam_registration_number IS NULL OR udyam_registration_number ~ '^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$');
