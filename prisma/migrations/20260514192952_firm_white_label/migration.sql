-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.


ALTER TYPE "UserRole" ADD VALUE 'PLATFORM_ADMIN';
ALTER TYPE "UserRole" ADD VALUE 'FIRM_ADMIN';

-- AlterTable
ALTER TABLE "Company" ADD COLUMN     "firmId" TEXT;

-- AlterTable
ALTER TABLE "User" ADD COLUMN     "firmId" TEXT;

-- CreateTable
CREATE TABLE "Firm" (
    "id" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "productName" TEXT NOT NULL,
    "customDomain" TEXT,
    "isDefault" BOOLEAN NOT NULL DEFAULT false,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "logoUrl" TEXT,
    "faviconUrl" TEXT,
    "primaryColor" TEXT NOT NULL DEFAULT '#1f2937',
    "accentColor" TEXT NOT NULL DEFAULT '#2563eb',
    "supportEmail" TEXT,
    "footerText" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Firm_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Firm_slug_key" ON "Firm"("slug");

-- CreateIndex
CREATE UNIQUE INDEX "Firm_customDomain_key" ON "Firm"("customDomain");

-- CreateIndex
CREATE INDEX "Firm_customDomain_idx" ON "Firm"("customDomain");

-- CreateIndex
CREATE INDEX "Company_firmId_idx" ON "Company"("firmId");

-- CreateIndex
CREATE INDEX "User_firmId_idx" ON "User"("firmId");

-- AddForeignKey
ALTER TABLE "User" ADD CONSTRAINT "User_firmId_fkey" FOREIGN KEY ("firmId") REFERENCES "Firm"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Company" ADD CONSTRAINT "Company_firmId_fkey" FOREIGN KEY ("firmId") REFERENCES "Firm"("id") ON DELETE SET NULL ON UPDATE CASCADE;
