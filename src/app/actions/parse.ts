"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import { readUpload } from "@/lib/storage";
import { recordAudit } from "@/lib/audit";
import { callParser, type ParseResponse, type FieldSlot } from "@/lib/parser-client";

/**
 * Run a Document through the parser sidecar and store the structured extract
 * in `Document.parsedPayload`. Redirects to the review page.
 */
export async function parseDocument(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const documentId = String(formData.get("documentId") || "");
  const hintForm = (formData.get("hintForm") as string | null) || null;
  if (!documentId) throw new Error("Missing documentId");

  const doc = await prisma.document.findUnique({ where: { id: documentId } });
  if (!doc || doc.companyId !== company.id) throw new Error("Not found");

  const bytes = await readUpload(doc.storageKey);
  const result: ParseResponse = await callParser(doc.title, bytes, doc.mimeType, hintForm);

  await prisma.document.update({
    where: { id: documentId },
    data: { parsedPayload: result as unknown as object, source: "parsed" },
  });
  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "Document",
    entityId: documentId,
    action: "update",
    after: { parsed: true, playbook: result.playbook, matched: result.matched },
  });

  revalidatePath("/company/documents");
  redirect(`/company/documents/${documentId}/review`);
}

// ---------- Apply accepted fields to master ----------
// Each entity has its own action so users can apply piece-by-piece if they want.
// All actions are idempotent within reason (Filing/Address etc. are append-only by design).

function picks(formData: FormData, prefix: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of formData.entries()) {
    if (k.startsWith(prefix + ".")) {
      const field = k.slice(prefix.length + 1);
      const val = typeof v === "string" ? v : "";
      if (val.trim() !== "") out[field] = val;
    }
  }
  return out;
}

export async function applyParsedFiling(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const documentId = String(formData.get("documentId") || "");
  const f = picks(formData, "filing");
  if (!f.form) throw new Error("Form number is required");

  const filing = await prisma.filing.create({
    data: {
      companyId: company.id,
      form: f.form,
      srn: f.srn || null,
      fy: f.fy || null,
      purpose: f.purpose || null,
      amountPaid: f.amountPaid ? f.amountPaid : null,
      filedOn: f.filedOn ? new Date(f.filedOn) : null,
      status: (f.status as never) || "FILED",
      remarks: `Parsed from document ${documentId}`,
    },
  });
  if (documentId) {
    await prisma.document.update({
      where: { id: documentId },
      data: { filingId: filing.id, attachmentRole: "FORM", category: "FILING" },
    });
  }
  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "Filing",
    entityId: filing.id,
    action: "create",
    after: filing,
  });
  revalidatePath("/company/filings");
  revalidatePath(`/company/documents/${documentId}/review`);
}

export async function applyParsedAddress(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const a = picks(formData, "address");
  if (!a.line1 || !a.city || !a.state || !a.pin || !a.effectiveFrom) {
    throw new Error("Address requires line1, city, state, pin, effectiveFrom");
  }
  const effFrom = new Date(a.effectiveFrom);
  const type = (a.type as never) || "REGISTERED";
  await prisma.address.updateMany({
    where: { companyId: company.id, type, effectiveTo: null },
    data: { effectiveTo: effFrom },
  });
  const created = await prisma.address.create({
    data: {
      companyId: company.id,
      type,
      line1: a.line1,
      line2: a.line2 || null,
      city: a.city,
      state: a.state,
      pin: a.pin,
      country: a.country || "India",
      email: a.email || null,
      phone: a.phone || null,
      effectiveFrom: effFrom,
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
}

export async function applyParsedCapital(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const c = picks(formData, "capital");
  if (!c.authorizedAmount || !c.paidUpAmount || !c.faceValue || !c.effectiveFrom) {
    throw new Error("Capital requires authorizedAmount, paidUpAmount, faceValue, effectiveFrom");
  }
  const effFrom = new Date(c.effectiveFrom);
  await prisma.capitalHistory.updateMany({
    where: { companyId: company.id, effectiveTo: null },
    data: { effectiveTo: effFrom },
  });
  const created = await prisma.capitalHistory.create({
    data: {
      companyId: company.id,
      authorizedAmount: c.authorizedAmount,
      paidUpAmount: c.paidUpAmount,
      faceValue: c.faceValue,
      authorizedShares: BigInt(c.authorizedShares || "0"),
      paidUpShares: BigInt(c.paidUpShares || "0"),
      effectiveFrom: effFrom,
      changeReason: (c.changeReason as never) || "OTHER",
    },
  });
  await recordAudit({
    userId: user.id,
    companyId: company.id,
    entity: "CapitalHistory",
    entityId: created.id,
    action: "create",
    after: {
      ...created,
      authorizedShares: created.authorizedShares.toString(),
      paidUpShares: created.paidUpShares.toString(),
    },
  });
  revalidatePath("/company/capital");
}

export async function applyParsedDirector(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const d = picks(formData, "director");
  const ds = picks(formData, "directorship");
  if (!d.din || !d.name || !ds.designation || !ds.appointmentDate) {
    throw new Error("Director requires din, name, designation, appointmentDate");
  }
  const dir = await prisma.director.upsert({
    where: { din: d.din },
    create: {
      din: d.din,
      name: d.name,
      pan: d.pan || null,
      email: d.email || null,
      phone: d.phone || null,
      nationality: d.nationality || "Indian",
    },
    update: {
      name: d.name,
      pan: d.pan || undefined,
      email: d.email || undefined,
      phone: d.phone || undefined,
    },
  });
  const created = await prisma.directorship.create({
    data: {
      companyId: company.id,
      directorId: dir.id,
      designation: ds.designation as never,
      appointmentDate: new Date(ds.appointmentDate),
      cessationDate: ds.cessationDate ? new Date(ds.cessationDate) : null,
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
}

/**
 * Apply parsed MOA subscribers as ShareholderEntry OPENING_BALANCE rows.
 *
 * The review UI submits N rows like:
 *   subscriber.0.name, subscriber.0.shares, subscriber.0.address, ...
 *   subscriber.1.name, subscriber.1.shares, ...
 *
 * We resolve / create one Shareholder per name, then write one
 * ShareholdingEntry per row with transactionType=OPENING_BALANCE.
 */
export async function applyParsedSubscribers(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const asOfDate = String(formData.get("asOfDate") || "");
  const faceValueRaw = String(formData.get("faceValue") || "");
  if (!asOfDate || !faceValueRaw) {
    throw new Error("As-of date and face value are required to record subscribers");
  }
  const effectiveAsOf = new Date(asOfDate);

  // Collect rows from the multipart payload.
  const rows = new Map<number, Record<string, string>>();
  for (const [k, v] of formData.entries()) {
    const m = k.match(/^subscriber\.(\d+)\.(\w+)$/);
    if (!m) continue;
    const idx = Number(m[1]);
    const field = m[2];
    const val = typeof v === "string" ? v.trim() : "";
    if (!val) continue;
    if (!rows.has(idx)) rows.set(idx, {});
    rows.get(idx)![field] = val;
  }
  if (rows.size === 0) throw new Error("No subscribers selected");

  let created = 0;
  for (const [, row] of [...rows.entries()].sort((a, b) => a[0] - b[0])) {
    if (!row.name || !row.shares) continue;
    const sharesNum = BigInt(row.shares.replace(/[, ]+/g, ""));
    if (sharesNum <= 0n) continue;

    const existing = await prisma.shareholder.findFirst({
      where: {
        companyId: company.id,
        OR: [
          row.pan ? { pan: row.pan } : { name: row.name },
          { name: row.name },
        ],
      },
    });
    const sh =
      existing ??
      (await prisma.shareholder.create({
        data: {
          companyId: company.id,
          name: row.name,
          pan: row.pan || null,
          address: row.address || null,
          type: (row.type as never) || "INDIVIDUAL",
        },
      }));

    const entry = await prisma.shareholdingEntry.create({
      data: {
        companyId: company.id,
        shareholderId: sh.id,
        shareClass: (row.shareClass as never) || "EQUITY",
        transactionType: "OPENING_BALANCE",
        numberOfShares: sharesNum,
        faceValue: faceValueRaw,
        premium: null,
        asOfDate: effectiveAsOf,
        notes: "From MOA subscribers (parsed)",
      },
    });
    await recordAudit({
      userId: user.id,
      companyId: company.id,
      entity: "ShareholdingEntry",
      entityId: entry.id,
      action: "create",
      after: { ...entry, numberOfShares: entry.numberOfShares.toString() },
    });
    created++;
  }

  revalidatePath("/company/shareholding");
  revalidatePath("/dashboard");
  return { created };
}

/**
 * Bulk-apply parsed directors (e.g. from MCA21 Master Data) as Director +
 * Directorship rows. Existing DINs are upserted; new DINs get a fresh
 * Director row.
 */
export async function applyParsedDirectorsList(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const rows = new Map<number, Record<string, string>>();
  for (const [k, v] of formData.entries()) {
    const m = k.match(/^director\.(\d+)\.(\w+)$/);
    if (!m) continue;
    const idx = Number(m[1]);
    const field = m[2];
    const val = typeof v === "string" ? v.trim() : "";
    if (!val) continue;
    if (!rows.has(idx)) rows.set(idx, {});
    rows.get(idx)![field] = val;
  }
  if (rows.size === 0) throw new Error("No directors selected");

  let created = 0;
  for (const [, row] of [...rows.entries()].sort((a, b) => a[0] - b[0])) {
    if (!row.din || !row.name) continue;
    if (!/^\d{8}$/.test(row.din)) continue; // skip junk rows where the column is a PAN

    const director = await prisma.director.upsert({
      where: { din: row.din },
      create: {
        din: row.din,
        name: row.name,
        pan: row.pan || null,
        nationality: row.nationality || "Indian",
      },
      update: { name: row.name },
    });

    // Idempotency — don't create duplicate directorships for the same company / director / appointment date.
    const appointmentDate = row.appointmentDate ? new Date(row.appointmentDate) : new Date();
    const dupe = await prisma.directorship.findFirst({
      where: { companyId: company.id, directorId: director.id, appointmentDate },
    });
    if (dupe) continue;

    const entry = await prisma.directorship.create({
      data: {
        companyId: company.id,
        directorId: director.id,
        designation: (row.designation?.toUpperCase().replaceAll(" ", "_") as never) || "DIRECTOR",
        appointmentDate,
        cessationDate: row.cessationDate ? new Date(row.cessationDate) : null,
        notes: "From MCA Master Data (parsed)",
      },
    });
    await recordAudit({
      userId: user.id,
      companyId: company.id,
      entity: "Directorship",
      entityId: entry.id,
      action: "create",
      after: entry,
    });
    created++;
  }

  revalidatePath("/company/directors");
  revalidatePath("/dashboard");
  return { created };
}

export async function applyParsedCompany(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const c = picks(formData, "company");
  if (Object.keys(c).length === 0) throw new Error("Nothing to update");
  const before = await prisma.company.findUnique({ where: { id: company.id } });
  const updated = await prisma.company.update({
    where: { id: company.id },
    data: {
      ...(c.cin && { cin: c.cin.toUpperCase() }),
      ...(c.name && { name: c.name }),
      ...(c.pan && { pan: c.pan.toUpperCase() }),
      ...(c.tan && { tan: c.tan.toUpperCase() }),
      ...(c.gstin && { gstin: c.gstin.toUpperCase() }),
      ...(c.udyamNumber && { udyamNumber: c.udyamNumber.toUpperCase() }),
      ...(c.dpiitNumber && { dpiitNumber: c.dpiitNumber.toUpperCase() }),
      ...(c.iecNumber && { iecNumber: c.iecNumber }),
      ...(c.rocCode && { rocCode: c.rocCode }),
      ...(c.registrationNo && { registrationNo: c.registrationNo }),
      ...(c.dateOfIncorporation && { dateOfIncorporation: new Date(c.dateOfIncorporation) }),
      ...(c.mainNicCode && { mainNicCode: c.mainNicCode }),
      ...(c.businessNature && { businessNature: c.businessNature }),
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

export async function applyParsedShareholding(formData: FormData) {
  const { user, company } = await requireActiveCompany();
  const s = picks(formData, "shareholding");
  const name = s.shareholderName || s.name;
  if (!name || !s.numberOfShares || !s.faceValue || !s.asOfDate) {
    throw new Error("Shareholding requires shareholderName, numberOfShares, faceValue, asOfDate");
  }
  const existing = await prisma.shareholder.findFirst({
    where: { companyId: company.id, OR: [{ pan: s.pan || "" }, { name }] },
  });
  const sh = existing
    ? await prisma.shareholder.update({ where: { id: existing.id }, data: { name } })
    : await prisma.shareholder.create({
        data: {
          companyId: company.id,
          name,
          pan: s.pan || null,
          type: (s.type as never) || "INDIVIDUAL",
        },
      });
  const created = await prisma.shareholdingEntry.create({
    data: {
      companyId: company.id,
      shareholderId: sh.id,
      shareClass: (s.shareClass as never) || "EQUITY",
      transactionType: (s.transactionType as never) || "ALLOTMENT",
      numberOfShares: BigInt(s.numberOfShares),
      faceValue: s.faceValue,
      premium: s.premium || null,
      asOfDate: new Date(s.asOfDate),
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
