-- CreateEnum
CREATE TYPE "UserRole" AS ENUM ('ADMIN', 'STAFF', 'CLIENT');

-- CreateEnum
CREATE TYPE "MembershipRole" AS ENUM ('OWNER', 'EDITOR', 'VIEWER');

-- CreateEnum
CREATE TYPE "CompanyClass" AS ENUM ('PRIVATE', 'PUBLIC', 'OPC', 'LLP', 'SECTION_8');

-- CreateEnum
CREATE TYPE "CompanyStatus" AS ENUM ('ACTIVE', 'DORMANT', 'STRIKE_OFF', 'UNDER_LIQUIDATION', 'DISSOLVED', 'AMALGAMATED');

-- CreateEnum
CREATE TYPE "ListingStatus" AS ENUM ('UNLISTED', 'LISTED');

-- CreateEnum
CREATE TYPE "AddressType" AS ENUM ('REGISTERED', 'CORPORATE', 'CORRESPONDENCE', 'FACTORY', 'BRANCH');

-- CreateEnum
CREATE TYPE "CapitalChangeReason" AS ENUM ('INITIAL', 'ALLOTMENT', 'BUYBACK', 'BONUS', 'SPLIT', 'CONSOLIDATION', 'REDUCTION', 'CONVERSION', 'OTHER');

-- CreateEnum
CREATE TYPE "DirectorDesignation" AS ENUM ('DIRECTOR', 'MANAGING_DIRECTOR', 'WHOLE_TIME_DIRECTOR', 'INDEPENDENT_DIRECTOR', 'NOMINEE_DIRECTOR', 'ADDITIONAL_DIRECTOR', 'ALTERNATE_DIRECTOR', 'CHAIRMAN', 'CFO', 'CS', 'CEO');

-- CreateEnum
CREATE TYPE "ShareholderType" AS ENUM ('INDIVIDUAL', 'BODY_CORPORATE', 'HUF', 'FOREIGN_INDIVIDUAL', 'FOREIGN_CORPORATE', 'TRUST', 'GOVERNMENT');

-- CreateEnum
CREATE TYPE "ShareClass" AS ENUM ('EQUITY', 'PREFERENCE', 'CCPS', 'OCPS');

-- CreateEnum
CREATE TYPE "ShareTransactionType" AS ENUM ('ALLOTMENT', 'TRANSFER_IN', 'TRANSFER_OUT', 'BUYBACK', 'BONUS', 'SPLIT', 'CONVERSION', 'OPENING_BALANCE');

-- CreateEnum
CREATE TYPE "DocumentCategory" AS ENUM ('MASTER', 'YEARLY', 'FILING', 'OTHER');

-- CreateEnum
CREATE TYPE "DocumentType" AS ENUM ('CIN_CERTIFICATE', 'MOA', 'AOA', 'PAN_CARD', 'TAN_CERTIFICATE', 'GST_CERTIFICATE', 'COMMON_SEAL', 'REGISTERED_OFFICE_PROOF', 'BOARD_RESOLUTION', 'ITR', 'FINANCIALS_AUDITED', 'FINANCIALS_PROVISIONAL', 'AOC_4', 'MGT_7', 'MGT_7A', 'DIR_3_KYC', 'BOARD_REPORT', 'AGM_MINUTES', 'SIGNIFICANT_NOTES', 'AUDITORS_REPORT', 'FORM_INC_22', 'FORM_DIR_12', 'FORM_SH_7', 'FORM_PAS_3', 'FORM_MGT_14', 'CHALLAN', 'OTHER');

-- CreateEnum
CREATE TYPE "FilingStatus" AS ENUM ('PENDING', 'FILED', 'APPROVED', 'REJECTED', 'RESUBMITTED');

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "name" TEXT,
    "role" "UserRole" NOT NULL DEFAULT 'STAFF',
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Membership" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "role" "MembershipRole" NOT NULL DEFAULT 'VIEWER',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Membership_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Company" (
    "id" TEXT NOT NULL,
    "cin" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "formerNames" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "pan" TEXT,
    "tan" TEXT,
    "gstin" TEXT,
    "rocCode" TEXT,
    "registrationNo" TEXT,
    "dateOfIncorporation" TIMESTAMP(3),
    "emailOfficial" TEXT,
    "phoneOfficial" TEXT,
    "website" TEXT,
    "companyClass" "CompanyClass" NOT NULL DEFAULT 'PRIVATE',
    "status" "CompanyStatus" NOT NULL DEFAULT 'ACTIVE',
    "listingStatus" "ListingStatus" NOT NULL DEFAULT 'UNLISTED',
    "mainNicCode" TEXT,
    "businessNature" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Company_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Address" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "type" "AddressType" NOT NULL DEFAULT 'REGISTERED',
    "line1" TEXT NOT NULL,
    "line2" TEXT,
    "city" TEXT NOT NULL,
    "state" TEXT NOT NULL,
    "pin" TEXT NOT NULL,
    "country" TEXT NOT NULL DEFAULT 'India',
    "email" TEXT,
    "phone" TEXT,
    "effectiveFrom" TIMESTAMP(3) NOT NULL,
    "effectiveTo" TIMESTAMP(3),
    "changeFiling" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Address_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CapitalHistory" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "authorizedAmount" DECIMAL(18,2) NOT NULL,
    "paidUpAmount" DECIMAL(18,2) NOT NULL,
    "faceValue" DECIMAL(18,2) NOT NULL,
    "authorizedShares" BIGINT NOT NULL,
    "paidUpShares" BIGINT NOT NULL,
    "effectiveFrom" TIMESTAMP(3) NOT NULL,
    "effectiveTo" TIMESTAMP(3),
    "changeReason" "CapitalChangeReason" NOT NULL DEFAULT 'INITIAL',
    "changeFiling" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CapitalHistory_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Director" (
    "id" TEXT NOT NULL,
    "din" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "pan" TEXT,
    "dob" TIMESTAMP(3),
    "nationality" TEXT DEFAULT 'Indian',
    "email" TEXT,
    "phone" TEXT,
    "address" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Director_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Directorship" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "directorId" TEXT NOT NULL,
    "designation" "DirectorDesignation" NOT NULL DEFAULT 'DIRECTOR',
    "appointmentDate" TIMESTAMP(3) NOT NULL,
    "cessationDate" TIMESTAMP(3),
    "appointmentMode" TEXT,
    "cessationMode" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Directorship_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Shareholder" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "pan" TEXT,
    "folio" TEXT,
    "type" "ShareholderType" NOT NULL DEFAULT 'INDIVIDUAL',
    "nationality" TEXT DEFAULT 'Indian',
    "address" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Shareholder_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ShareholdingEntry" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "shareholderId" TEXT NOT NULL,
    "shareClass" "ShareClass" NOT NULL DEFAULT 'EQUITY',
    "transactionType" "ShareTransactionType" NOT NULL,
    "numberOfShares" BIGINT NOT NULL,
    "faceValue" DECIMAL(18,2) NOT NULL,
    "premium" DECIMAL(18,2),
    "asOfDate" TIMESTAMP(3) NOT NULL,
    "filingReference" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ShareholdingEntry_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Document" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "category" "DocumentCategory" NOT NULL,
    "docType" "DocumentType" NOT NULL,
    "title" TEXT NOT NULL,
    "fy" TEXT,
    "storageKey" TEXT NOT NULL,
    "mimeType" TEXT,
    "sizeBytes" INTEGER,
    "checksum" TEXT,
    "uploadedById" TEXT NOT NULL,
    "source" TEXT NOT NULL DEFAULT 'manual',
    "parsedPayload" JSONB,
    "version" INTEGER NOT NULL DEFAULT 1,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Document_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Filing" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "form" TEXT NOT NULL,
    "srn" TEXT,
    "fy" TEXT,
    "filedOn" TIMESTAMP(3),
    "status" "FilingStatus" NOT NULL DEFAULT 'PENDING',
    "remarks" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Filing_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AuditLog" (
    "id" TEXT NOT NULL,
    "companyId" TEXT,
    "userId" TEXT,
    "entity" TEXT NOT NULL,
    "entityId" TEXT,
    "action" TEXT NOT NULL,
    "before" JSONB,
    "after" JSONB,
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AuditLog_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "Membership_companyId_idx" ON "Membership"("companyId");

-- CreateIndex
CREATE UNIQUE INDEX "Membership_userId_companyId_key" ON "Membership"("userId", "companyId");

-- CreateIndex
CREATE UNIQUE INDEX "Company_cin_key" ON "Company"("cin");

-- CreateIndex
CREATE INDEX "Address_companyId_type_effectiveTo_idx" ON "Address"("companyId", "type", "effectiveTo");

-- CreateIndex
CREATE INDEX "CapitalHistory_companyId_effectiveTo_idx" ON "CapitalHistory"("companyId", "effectiveTo");

-- CreateIndex
CREATE UNIQUE INDEX "Director_din_key" ON "Director"("din");

-- CreateIndex
CREATE INDEX "Directorship_companyId_cessationDate_idx" ON "Directorship"("companyId", "cessationDate");

-- CreateIndex
CREATE UNIQUE INDEX "Directorship_companyId_directorId_appointmentDate_key" ON "Directorship"("companyId", "directorId", "appointmentDate");

-- CreateIndex
CREATE INDEX "Shareholder_companyId_idx" ON "Shareholder"("companyId");

-- CreateIndex
CREATE INDEX "Shareholder_companyId_pan_idx" ON "Shareholder"("companyId", "pan");

-- CreateIndex
CREATE INDEX "ShareholdingEntry_companyId_asOfDate_idx" ON "ShareholdingEntry"("companyId", "asOfDate");

-- CreateIndex
CREATE INDEX "ShareholdingEntry_companyId_shareholderId_shareClass_idx" ON "ShareholdingEntry"("companyId", "shareholderId", "shareClass");

-- CreateIndex
CREATE INDEX "Document_companyId_category_idx" ON "Document"("companyId", "category");

-- CreateIndex
CREATE INDEX "Document_companyId_docType_fy_idx" ON "Document"("companyId", "docType", "fy");

-- CreateIndex
CREATE INDEX "Filing_companyId_form_idx" ON "Filing"("companyId", "form");

-- CreateIndex
CREATE INDEX "AuditLog_companyId_entity_createdAt_idx" ON "AuditLog"("companyId", "entity", "createdAt");

-- CreateIndex
CREATE INDEX "AuditLog_userId_createdAt_idx" ON "AuditLog"("userId", "createdAt");

-- AddForeignKey
ALTER TABLE "Membership" ADD CONSTRAINT "Membership_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Membership" ADD CONSTRAINT "Membership_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Address" ADD CONSTRAINT "Address_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CapitalHistory" ADD CONSTRAINT "CapitalHistory_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Directorship" ADD CONSTRAINT "Directorship_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Directorship" ADD CONSTRAINT "Directorship_directorId_fkey" FOREIGN KEY ("directorId") REFERENCES "Director"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Shareholder" ADD CONSTRAINT "Shareholder_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ShareholdingEntry" ADD CONSTRAINT "ShareholdingEntry_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ShareholdingEntry" ADD CONSTRAINT "ShareholdingEntry_shareholderId_fkey" FOREIGN KEY ("shareholderId") REFERENCES "Shareholder"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Document" ADD CONSTRAINT "Document_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Document" ADD CONSTRAINT "Document_uploadedById_fkey" FOREIGN KEY ("uploadedById") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Filing" ADD CONSTRAINT "Filing_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuditLog" ADD CONSTRAINT "AuditLog_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuditLog" ADD CONSTRAINT "AuditLog_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;
