"use server";

import { revalidatePath } from "next/cache";
import bcrypt from "bcryptjs";
import { z } from "zod";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";
import { recordAudit } from "@/lib/audit";

async function requireAdmin() {
  const u = await requireUser();
  if (u.role !== "ADMIN") throw new Error("Forbidden");
  return u;
}

export async function createCompany(formData: FormData) {
  const admin = await requireAdmin();
  const name = String(formData.get("name") || "").trim();
  const cin = String(formData.get("cin") || "").trim().toUpperCase();
  if (!name || !cin) throw new Error("Missing fields");
  const created = await prisma.company.create({ data: { name, cin, companyClass: "PRIVATE" } });
  await recordAudit({ userId: admin.id, companyId: created.id, entity: "Company", entityId: created.id, action: "create", after: created });
  revalidatePath("/admin");
}

const UserSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().optional(),
  role: z.enum(["ADMIN", "STAFF", "CLIENT"]),
});

export async function createUser(formData: FormData) {
  await requireAdmin();
  const parsed = UserSchema.parse(Object.fromEntries(formData.entries()));
  const passwordHash = await bcrypt.hash(parsed.password, 10);
  await prisma.user.create({
    data: {
      email: parsed.email.toLowerCase().trim(),
      passwordHash,
      name: parsed.name || null,
      role: parsed.role,
    },
  });
  revalidatePath("/admin");
}

export async function grantMembership(formData: FormData) {
  await requireAdmin();
  const userId = String(formData.get("userId") || "");
  const companyId = String(formData.get("companyId") || "");
  const role = String(formData.get("role") || "VIEWER") as "OWNER" | "EDITOR" | "VIEWER";
  if (!userId || !companyId) throw new Error("Missing fields");
  await prisma.membership.upsert({
    where: { userId_companyId: { userId, companyId } },
    create: { userId, companyId, role },
    update: { role },
  });
  revalidatePath("/admin");
}
