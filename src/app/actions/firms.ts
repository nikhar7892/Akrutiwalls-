"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { z } from "zod";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";
import { recordAudit } from "@/lib/audit";
import { FIRM_OVERRIDE_COOKIE } from "@/lib/firm";

async function requirePlatformAdmin() {
  const u = await requireUser();
  if (u.role !== "PLATFORM_ADMIN" && u.role !== "ADMIN") throw new Error("Forbidden");
  return u;
}

const FirmSchema = z.object({
  slug: z.string().min(2).regex(/^[a-z0-9-]+$/, "lowercase letters, digits, and hyphens only"),
  name: z.string().min(2),
  productName: z.string().min(2),
  customDomain: z.string().optional().nullable(),
  logoUrl: z.string().optional().nullable(),
  faviconUrl: z.string().optional().nullable(),
  primaryColor: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(),
  accentColor: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(),
  supportEmail: z.string().email().optional().or(z.literal("")).nullable(),
  footerText: z.string().optional().nullable(),
  isActive: z.preprocess((v) => v === "on" || v === "true" || v === true, z.boolean()).optional(),
});

export async function createFirm(formData: FormData) {
  const admin = await requirePlatformAdmin();
  const parsed = FirmSchema.parse({
    slug: formData.get("slug"),
    name: formData.get("name"),
    productName: formData.get("productName"),
    customDomain: formData.get("customDomain") || null,
    primaryColor: formData.get("primaryColor") || "#1f2937",
    accentColor: formData.get("accentColor") || "#2563eb",
    supportEmail: formData.get("supportEmail") || null,
    footerText: formData.get("footerText") || null,
    isActive: formData.get("isActive") ?? true,
  });
  const created = await prisma.firm.create({
    data: {
      slug: parsed.slug,
      name: parsed.name,
      productName: parsed.productName,
      customDomain: parsed.customDomain || null,
      primaryColor: parsed.primaryColor || "#1f2937",
      accentColor: parsed.accentColor || "#2563eb",
      supportEmail: parsed.supportEmail || null,
      footerText: parsed.footerText || null,
      isActive: parsed.isActive ?? true,
    },
  });
  await recordAudit({
    userId: admin.id,
    entity: "Firm",
    entityId: created.id,
    action: "create",
    after: created,
  });
  revalidatePath("/admin/firms");
}

export async function updateFirm(formData: FormData) {
  const admin = await requirePlatformAdmin();
  const id = String(formData.get("id") || "");
  if (!id) throw new Error("Missing id");

  const parsed = FirmSchema.partial().parse({
    slug: formData.get("slug") || undefined,
    name: formData.get("name") || undefined,
    productName: formData.get("productName") || undefined,
    customDomain: formData.get("customDomain") || null,
    logoUrl: formData.get("logoUrl") || null,
    faviconUrl: formData.get("faviconUrl") || null,
    primaryColor: formData.get("primaryColor") || undefined,
    accentColor: formData.get("accentColor") || undefined,
    supportEmail: formData.get("supportEmail") || null,
    footerText: formData.get("footerText") || null,
    isActive: formData.get("isActive") ?? undefined,
  });

  const before = await prisma.firm.findUnique({ where: { id } });
  const updated = await prisma.firm.update({
    where: { id },
    data: {
      ...(parsed.slug && { slug: parsed.slug }),
      ...(parsed.name && { name: parsed.name }),
      ...(parsed.productName && { productName: parsed.productName }),
      customDomain: parsed.customDomain || null,
      logoUrl: parsed.logoUrl || null,
      faviconUrl: parsed.faviconUrl || null,
      ...(parsed.primaryColor && { primaryColor: parsed.primaryColor }),
      ...(parsed.accentColor && { accentColor: parsed.accentColor }),
      supportEmail: parsed.supportEmail || null,
      footerText: parsed.footerText || null,
      ...(parsed.isActive !== undefined && { isActive: parsed.isActive }),
    },
  });
  await recordAudit({
    userId: admin.id,
    entity: "Firm",
    entityId: id,
    action: "update",
    before,
    after: updated,
  });
  revalidatePath("/admin/firms");
  revalidatePath(`/admin/firms/${id}`);
}

export async function moveCompanyToFirm(formData: FormData) {
  await requirePlatformAdmin();
  const companyId = String(formData.get("companyId") || "");
  const firmId = String(formData.get("firmId") || "");
  if (!companyId || !firmId) throw new Error("Missing fields");
  await prisma.company.update({ where: { id: companyId }, data: { firmId } });
  revalidatePath("/admin");
  revalidatePath("/admin/firms");
}

export async function moveUserToFirm(formData: FormData) {
  await requirePlatformAdmin();
  const userId = String(formData.get("userId") || "");
  const firmId = String(formData.get("firmId") || "");
  if (!userId || !firmId) throw new Error("Missing fields");
  await prisma.user.update({ where: { id: userId }, data: { firmId } });
  revalidatePath("/admin");
  revalidatePath("/admin/firms");
}

/** Dev-time helper: switch which firm the current browser session "is" (by slug). */
export async function setDevFirmOverride(formData: FormData) {
  await requirePlatformAdmin();
  const slug = String(formData.get("slug") || "").trim();
  if (slug) {
    cookies().set(FIRM_OVERRIDE_COOKIE, slug, {
      httpOnly: false,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 8,
    });
  } else {
    cookies().delete(FIRM_OVERRIDE_COOKIE);
  }
  revalidatePath("/admin");
}
