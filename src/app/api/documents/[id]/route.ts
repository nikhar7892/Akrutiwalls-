import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { requireUser, assertCompanyAccess } from "@/lib/session";
import { readUpload } from "@/lib/storage";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const user = await requireUser();
  const doc = await prisma.document.findUnique({ where: { id: params.id } });
  if (!doc) return new NextResponse("Not found", { status: 404 });
  await assertCompanyAccess(user.id, doc.companyId);
  const buf = await readUpload(doc.storageKey);
  return new NextResponse(buf as unknown as BodyInit, {
    headers: {
      "Content-Type": doc.mimeType || "application/octet-stream",
      "Content-Disposition": `inline; filename="${encodeURIComponent(doc.title)}"`,
      "Cache-Control": "private, no-store",
    },
  });
}
