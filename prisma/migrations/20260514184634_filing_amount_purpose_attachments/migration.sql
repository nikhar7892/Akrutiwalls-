-- CreateEnum
CREATE TYPE "FilingAttachmentRole" AS ENUM ('FORM', 'CHALLAN', 'OTHER');

-- AlterTable
ALTER TABLE "Document" ADD COLUMN     "attachmentRole" "FilingAttachmentRole",
ADD COLUMN     "filingId" TEXT;

-- AlterTable
ALTER TABLE "Filing" ADD COLUMN     "amountPaid" DECIMAL(18,2),
ADD COLUMN     "purpose" TEXT;

-- CreateIndex
CREATE INDEX "Document_filingId_idx" ON "Document"("filingId");

-- CreateIndex
CREATE INDEX "Filing_companyId_srn_idx" ON "Filing"("companyId", "srn");

-- AddForeignKey
ALTER TABLE "Document" ADD CONSTRAINT "Document_filingId_fkey" FOREIGN KEY ("filingId") REFERENCES "Filing"("id") ON DELETE SET NULL ON UPDATE CASCADE;
