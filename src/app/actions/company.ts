"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";
import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import { recordAudit } from "@/lib/audit";
import { saveUpload } from "@/lib/storage";

// ---------- Identity ----------

const IdentitySchema = z.object({
  name: z.string().min(2),
  cin: z.string().regex(/^[A-Z]{1}\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$/i, "Invalid CIN format"),
  pan: z.string().optional().nullable(),
  tan: z.string().optional().nullable(),
  gstin: z.string().optional().nullable(),
  rocCode: z.string().optional().nullable(),
  registrationNo: z.string().optional().nullable(),
  dateOfIncorporation: z.string().optional().nullable(),
  emailOfficial: z.string().email().optional().or(z.literal("")).nullable(),
  phoneOfficial: z.string().optional().nullable(),
  website: z.string().optional().nullable(),
  companyClass: z.enum(["PRIVATE", "PUBLIC", "OPC", "LLP", "SECTION_8"]),
  status: z.enum(["ACTIVE", "DORMANT", "STRIKE_OFF", "UNDER_LIQUIDATION", "DISSOLVED", "AMALGAMATED"]),
  listingStatus: z.enum(["UNLISTED", "LISTED"]),
  mainNicCode: z.string().optional().nullable(),
  businessNature: z.string().optional().nullable(),
});

export async function saveIdentity(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const raw = Object.fromEntries(formData.entries());
  const parsed = IdentitySchema.parse({
    ...raw,
    dateOfIncorporation: raw.dateOfIncorporation || null,
  });
  const before = await prisma.company.findUnique({ where: { id: company.id } });
  const updated = await prisma.company.update({
    where: { id: company.id },
    data: {
      ...parsed,
      cin: parsed.cin.toUpperCase(),
      dateOfIncorporation: parsed.dateOfIncorporation ? new Date(parsed.dateOfIncorporation) : null,
      emailOfficial: parsed.emailOfficial || null,
    },
  });
  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "Company",
    entityId: company.id,
    action: "update",
    before,
    after: updated,
  });
  revalidatePath("/company/identity");
  revalidatePath("/dashboard");
}

// ---------- Address ----------

const AddressSchema = z.object({
  type: z.enum(["REGISTERED", "CORPORATE", "CORRESPONDENCE", "FACTORY", "BRANCH"]),
  line1: z.string().min(2),
  line2: z.string().optional().nullable(),
  city: z.string().min(1),
  state: z.string().min(1),
  pin: z.string().regex(/^\d{6}$/, "PIN must be 6 digits"),
  country: z.string().default("India"),
  email: z.string().email().optional().or(z.literal("")).nullable(),
  phone: z.string().optional().nullable(),
  effectiveFrom: z.string(),
  changeFiling: z.string().optional().nullable(),
  notes: z.string().optional().nullable(),
});

export async function addAddress(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const raw = Object.fromEntries(formData.entries());
  const parsed = AddressSchema.parse(raw);
  const effFrom = new Date(parsed.effectiveFrom);
  // Close any open same-type address
  await prisma.address.updateMany({
    where: { companyId: company.id, type: parsed.type, effectiveTo: null },
    data: { effectiveTo: effFrom },
  });
  const created = await prisma.address.create({
    data: {
      companyId: company.id,
      type: parsed.type,
      line1: parsed.line1,
      line2: parsed.line2 || null,
      city: parsed.city,
      state: parsed.state,
      pin: parsed.pin,
      country: parsed.country || "India",
      email: parsed.email || null,
      phone: parsed.phone || null,
      effectiveFrom: effFrom,
      changeFiling: parsed.changeFiling || null,
      notes: parsed.notes || null,
    },
  });
  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "Address",
    entityId: created.id,
    action: "create",
    after: created,
  });
  revalidatePath("/company/address");
  revalidatePath("/dashboard");
}

// ---------- Capital ----------

const CapitalSchema = z.object({
  authorizedAmount: z.string(),
  paidUpAmount: z.string(),
  faceValue: z.string(),
  authorizedShares: z.string(),
  paidUpShares: z.string(),
  effectiveFrom: z.string(),
  changeReason: z.enum([
    "INITIAL",
    "ALLOTMENT",
    "BUYBACK",
    "BONUS",
    "SPLIT",
    "CONSOLIDATION",
    "REDUCTION",
    "CONVERSION",
    "OTHER",
  ]),
  changeFiling: z.string().optional().nullable(),
  notes: z.string().optional().nullable(),
});

export async function addCapitalChange(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const raw = Object.fromEntries(formData.entries());
  const parsed = CapitalSchema.parse(raw);
  const effFrom = new Date(parsed.effectiveFrom);
  await prisma.capitalHistory.updateMany({
    where: { companyId: company.id, effectiveTo: null },
    data: { effectiveTo: effFrom },
  });
  const created = await prisma.capitalHistory.create({
    data: {
      companyId: company.id,
      authorizedAmount: parsed.authorizedAmount,
      paidUpAmount: parsed.paidUpAmount,
      faceValue: parsed.faceValue,
      authorizedShares: BigInt(parsed.authorizedShares),
      paidUpShares: BigInt(parsed.paidUpShares),
      effectiveFrom: effFrom,
      changeReason: parsed.changeReason,
      changeFiling: parsed.changeFiling || null,
      notes: parsed.notes || null,
    },
  });
  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "CapitalHistory",
    entityId: created.id,
    action: "create",
    after: { ...created, authorizedShares: created.authorizedShares.toString(), paidUpShares: created.paidUpShares.toString() },
  });
  revalidatePath("/company/capital");
  revalidatePath("/dashboard");
}

// ---------- Directors ----------

const DirectorshipSchema = z.object({
  din: z.string().regex(/^\d{8}$/, "DIN must be 8 digits"),
  name: z.string().min(2),
  pan: z.string().optional().nullable(),
  dob: z.string().optional().nullable(),
  nationality: z.string().optional().nullable(),
  email: z.string().email().optional().or(z.literal("")).nullable(),
  phone: z.string().optional().nullable(),
  address: z.string().optional().nullable(),
  designation: z.enum([
    "DIRECTOR",
    "MANAGING_DIRECTOR",
    "WHOLE_TIME_DIRECTOR",
    "INDEPENDENT_DIRECTOR",
    "NOMINEE_DIRECTOR",
    "ADDITIONAL_DIRECTOR",
    "ALTERNATE_DIRECTOR",
    "CHAIRMAN",
    "CFO",
    "CS",
    "CEO",
  ]),
  appointmentDate: z.string(),
  appointmentMode: z.string().optional().nullable(),
});

export async function addDirectorship(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const raw = Object.fromEntries(formData.entries());
  const parsed = DirectorshipSchema.parse(raw);
  const director = await prisma.director.upsert({
    where: { din: parsed.din },
    create: {
      din: parsed.din,
      name: parsed.name,
      pan: parsed.pan || null,
      dob: parsed.dob ? new Date(parsed.dob) : null,
      nationality: parsed.nationality || "Indian",
      email: parsed.email || null,
      phone: parsed.phone || null,
      address: parsed.address || null,
    },
    update: {
      name: parsed.name,
      pan: parsed.pan || undefined,
      dob: parsed.dob ? new Date(parsed.dob) : undefined,
      email: parsed.email || undefined,
      phone: parsed.phone || undefined,
      address: parsed.address || undefined,
    },
  });
  const created = await prisma.directorship.create({
    data: {
      companyId: company.id,
      directorId: director.id,
      designation: parsed.designation,
      appointmentDate: new Date(parsed.appointmentDate),
      appointmentMode: parsed.appointmentMode || null,
    },
  });
  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "Directorship",
    entityId: created.id,
    action: "create",
    after: created,
  });
  revalidatePath("/company/directors");
  revalidatePath("/dashboard");
}

export async function endDirectorship(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const id = String(formData.get("id") || "");
  const cessationDate = String(formData.get("cessationDate") || "");
  const cessationMode = String(formData.get("cessationMode") || "") || null;
  if (!id || !cessationDate) throw new Error("Missing fields");
  const before = await prisma.directorship.findUnique({ where: { id } });
  if (!before || before.companyId !== company.id) throw new Error("Not found");
  const updated = await prisma.directorship.update({
    where: { id },
    data: { cessationDate: new Date(cessationDate), cessationMode },
  });
  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "Directorship",
    entityId: id,
    action: "update",
    before,
    after: updated,
  });
  revalidatePath("/company/directors");
}

// ---------- Shareholding ----------

const ShareholdingSchema = z.object({
  shareholderName: z.string().min(2),
  pan: z.string().optional().nullable(),
  folio: z.string().optional().nullable(),
  type: z.enum([
    "INDIVIDUAL",
    "BODY_CORPORATE",
    "HUF",
    "FOREIGN_INDIVIDUAL",
    "FOREIGN_CORPORATE",
    "TRUST",
    "GOVERNMENT",
  ]),
  shareClass: z.enum(["EQUITY", "PREFERENCE", "CCPS", "OCPS"]),
  transactionType: z.enum([
    "ALLOTMENT",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "BUYBACK",
    "BONUS",
    "SPLIT",
    "CONVERSION",
    "OPENING_BALANCE",
  ]),
  numberOfShares: z.string(),
  faceValue: z.string(),
  premium: z.string().optional().nullable(),
  asOfDate: z.string(),
  filingReference: z.string().optional().nullable(),
  notes: z.string().optional().nullable(),
});

export async function addShareholdingEntry(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const raw = Object.fromEntries(formData.entries());
  const parsed = ShareholdingSchema.parse(raw);
  const existing = await prisma.shareholder.findFirst({
    where: {
      companyId: company.id,
      OR: [
        parsed.pan ? { pan: parsed.pan } : { name: parsed.shareholderName },
        parsed.folio ? { folio: parsed.folio } : { name: parsed.shareholderName },
      ],
    },
  });
  const sh = existing
    ? await prisma.shareholder.update({
        where: { id: existing.id },
        data: { name: parsed.shareholderName, type: parsed.type },
      })
    : await prisma.shareholder.create({
        data: {
          companyId: company.id,
          name: parsed.shareholderName,
          pan: parsed.pan || null,
          folio: parsed.folio || null,
          type: parsed.type,
        },
      });
  const created = await prisma.shareholdingEntry.create({
    data: {
      companyId: company.id,
      shareholderId: sh.id,
      shareClass: parsed.shareClass,
      transactionType: parsed.transactionType,
      numberOfShares: BigInt(parsed.numberOfShares),
      faceValue: parsed.faceValue,
      premium: parsed.premium || null,
      asOfDate: new Date(parsed.asOfDate),
      filingReference: parsed.filingReference || null,
      notes: parsed.notes || null,
    },
  });
  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "ShareholdingEntry",
    entityId: created.id,
    action: "create",
    after: { ...created, numberOfShares: created.numberOfShares.toString() },
  });
  revalidatePath("/company/shareholding");
}

// ---------- Filings ----------

const FilingSchema = z.object({
  form: z.string().min(2),
  srn: z.string().optional().nullable(),
  purpose: z.string().optional().nullable(),
  amountPaid: z.string().optional().nullable(),
  fy: z.string().optional().nullable(),
  filedOn: z.string().optional().nullable(),
  status: z.enum(["PENDING", "FILED", "APPROVED", "REJECTED", "RESUBMITTED"]),
  remarks: z.string().optional().nullable(),
});

async function attachFile(
  companyId: string,
  userId: string,
  filingId: string,
  form: string,
  file: File,
  role: "FORM" | "CHALLAN" | "OTHER",
) {
  if (!file || file.size === 0) return null;
  const buffer = Buffer.from(await file.arrayBuffer());
  const stored = await saveUpload(companyId, file.name, buffer, file.type);
  return prisma.document.create({
    data: {
      companyId,
      category: "FILING",
      docType: role === "CHALLAN" ? "CHALLAN" : "OTHER",
      title: `${form} ${role === "FORM" ? "form" : role === "CHALLAN" ? "challan" : "attachment"} — ${file.name}`,
      storageKey: stored.storageKey,
      mimeType: stored.mimeType || null,
      sizeBytes: stored.sizeBytes,
      checksum: stored.checksum,
      uploadedById: userId,
      filingId,
      attachmentRole: role,
      source: "manual",
    },
  });
}

export async function addFiling(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const parsed = FilingSchema.parse({
    form: formData.get("form"),
    srn: formData.get("srn"),
    purpose: formData.get("purpose"),
    amountPaid: formData.get("amountPaid"),
    fy: formData.get("fy"),
    filedOn: formData.get("filedOn"),
    status: formData.get("status"),
    remarks: formData.get("remarks"),
  });
  const created = await prisma.filing.create({
    data: {
      companyId: company.id,
      form: parsed.form,
      srn: parsed.srn || null,
      purpose: parsed.purpose || null,
      amountPaid: parsed.amountPaid ? parsed.amountPaid : null,
      fy: parsed.fy || null,
      filedOn: parsed.filedOn ? new Date(parsed.filedOn) : null,
      status: parsed.status,
      remarks: parsed.remarks || null,
    },
  });

  const formFile = formData.get("formFile") as File | null;
  const challanFile = formData.get("challanFile") as File | null;
  if (formFile && formFile.size > 0) await attachFile(company.id, user.id, created.id, parsed.form, formFile, "FORM");
  if (challanFile && challanFile.size > 0) await attachFile(company.id, user.id, created.id, parsed.form, challanFile, "CHALLAN");

  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "Filing",
    entityId: created.id,
    action: "create",
    after: created,
  });
  revalidatePath("/company/filings");
  revalidatePath("/company/documents");
  revalidatePath("/dashboard");
}

export async function addFilingAttachment(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const filingId = String(formData.get("filingId") || "");
  const role = String(formData.get("role") || "OTHER") as "FORM" | "CHALLAN" | "OTHER";
  const file = formData.get("file") as File | null;
  if (!filingId || !file) throw new Error("Missing fields");
  const filing = await prisma.filing.findUnique({ where: { id: filingId } });
  if (!filing || filing.companyId !== company.id) throw new Error("Not found");
  await attachFile(company.id, user.id, filing.id, filing.form, file, role);
  revalidatePath("/company/filings");
  revalidatePath("/company/documents");
}

export async function deleteFilingAttachment(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const id = String(formData.get("id") || "");
  if (!id) throw new Error("Missing id");
  const doc = await prisma.document.findUnique({ where: { id } });
  if (!doc || doc.companyId !== company.id) throw new Error("Not found");
  await prisma.document.delete({ where: { id } });
  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "Document",
    entityId: id,
    action: "delete",
    before: { id: doc.id, title: doc.title, filingId: doc.filingId },
  });
  revalidatePath("/company/filings");
  revalidatePath("/company/documents");
}
