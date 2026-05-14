"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";
import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import { saveUpload } from "@/lib/storage";
import { recordAudit } from "@/lib/audit";

const DocSchema = z.object({
  category: z.enum(["MASTER", "YEARLY", "FILING", "OTHER"]),
  docType: z.string().min(1),
  title: z.string().min(1),
  fy: z.string().optional().nullable(),
  notes: z.string().optional().nullable(),
});

export async function uploadDocument(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const file = formData.get("file") as File | null;
  if (!file || file.size === 0) throw new Error("No file uploaded");
  const meta = DocSchema.parse({
    category: formData.get("category"),
    docType: formData.get("docType"),
    title: formData.get("title"),
    fy: formData.get("fy") || null,
    notes: formData.get("notes") || null,
  });

  const buffer = Buffer.from(await file.arrayBuffer());
  const stored = await saveUpload(company.id, file.name, buffer, file.type);

  const created = await prisma.document.create({
    data: {
      companyId: company.id,
      category: meta.category,
      docType: meta.docType as never,
      title: meta.title,
      fy: meta.fy || null,
      storageKey: stored.storageKey,
      mimeType: stored.mimeType || null,
      sizeBytes: stored.sizeBytes,
      checksum: stored.checksum,
      uploadedById: user.id,
      source: "manual",
      notes: meta.notes || null,
    },
  });

  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "Document",
    entityId: created.id,
    action: "create",
    after: { id: created.id, title: created.title, docType: created.docType, fy: created.fy },
  });

  revalidatePath("/company/documents");
  revalidatePath("/dashboard");
}
