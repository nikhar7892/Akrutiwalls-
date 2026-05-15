-- CreateTable
CREATE TABLE "parser_moa_clauses" (
    "cin" TEXT NOT NULL,
    "clause_roman" TEXT NOT NULL,
    "clause_title" TEXT NOT NULL,
    "clause_text" TEXT NOT NULL,
    "sub_clauses" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "parser_moa_clauses_pkey" PRIMARY KEY ("cin","clause_roman")
);

-- CreateTable
CREATE TABLE "parser_aoa_clauses" (
    "cin" TEXT NOT NULL,
    "article_no" TEXT NOT NULL,
    "article_title" TEXT NOT NULL,
    "clause_no" TEXT NOT NULL,
    "clause_text" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "parser_aoa_clauses_pkey" PRIMARY KEY ("cin","article_no","article_title","clause_no")
);

-- CreateTable
CREATE TABLE "parser_inconsistencies" (
    "id" TEXT NOT NULL,
    "cin" TEXT,
    "severity" TEXT NOT NULL,
    "rule" TEXT NOT NULL,
    "source_doc_type" TEXT NOT NULL,
    "source_doc_id" TEXT,
    "field" TEXT,
    "expected" TEXT,
    "found" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "parser_inconsistencies_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "parser_inconsistencies_cin_idx" ON "parser_inconsistencies"("cin");

-- CreateIndex
CREATE INDEX "parser_inconsistencies_severity_idx" ON "parser_inconsistencies"("severity");

-- AddForeignKey
ALTER TABLE "parser_moa_clauses" ADD CONSTRAINT "parser_moa_clauses_cin_fkey" FOREIGN KEY ("cin") REFERENCES "parser_company"("cin") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "parser_aoa_clauses" ADD CONSTRAINT "parser_aoa_clauses_cin_fkey" FOREIGN KEY ("cin") REFERENCES "parser_company"("cin") ON DELETE CASCADE ON UPDATE CASCADE;
