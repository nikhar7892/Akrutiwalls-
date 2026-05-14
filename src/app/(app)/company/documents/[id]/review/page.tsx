import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import {
  applyParsedAddress,
  applyParsedCapital,
  applyParsedCompany,
  applyParsedDirector,
  applyParsedFiling,
  applyParsedShareholding,
  parseDocument,
} from "@/app/actions/parse";

export const dynamic = "force-dynamic";

type FieldSlot = { value: unknown; source: string; confidence: number };
type EntityFields = Record<string, FieldSlot>;
type Extract = Record<string, EntityFields | unknown>;

type Section = {
  key: string;
  label: string;
  description: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  action: (fd: FormData) => any;
  entities: string[]; // first entity is primary; extras pulled too
};

const SECTIONS: Section[] = [
  {
    key: "company",
    label: "Company identity",
    description: "Updates the active company's master (CIN, PAN, TAN, GSTIN, Udyam, DPIIT, IEC, etc.).",
    action: applyParsedCompany,
    entities: ["company"],
  },
  {
    key: "filing",
    label: "MCA Filing",
    description: "Logs an entry in the Filings tab.",
    action: applyParsedFiling,
    entities: ["filing"],
  },
  {
    key: "address",
    label: "Address",
    description: "Adds a versioned address row; auto-closes the prior current one.",
    action: applyParsedAddress,
    entities: ["address"],
  },
  {
    key: "capital",
    label: "Capital",
    description: "Appends a new capital snapshot.",
    action: applyParsedCapital,
    entities: ["capital"],
  },
  {
    key: "director",
    label: "Director appointment",
    description: "Adds the director master + the directorship in one shot.",
    action: applyParsedDirector,
    entities: ["director", "directorship"],
  },
  {
    key: "shareholding",
    label: "Shareholding",
    description: "Records an entry in the share ledger.",
    action: applyParsedShareholding,
    entities: ["shareholding"],
  },
];

export default async function ReviewPage({ params }: { params: { id: string } }) {
  const { company } = await requireActiveCompany();
  const doc = await prisma.document.findUnique({ where: { id: params.id } });
  if (!doc || doc.companyId !== company.id) notFound();

  const payload = (doc.parsedPayload as Record<string, unknown> | null) || null;
  const matched = Boolean(payload?.matched);
  const playbook = (payload?.playbook as string) || null;
  const confidence = (payload?.confidence as string) || "none";
  const extracted: Extract = (payload?.extracted as Extract) || {};
  const warnings = (payload?.warnings as string[]) || [];
  const raw = (payload?.raw as Record<string, unknown>) || {};

  const renderable = SECTIONS.filter((s) =>
    s.entities.some((e) => isEntityFields(extracted[e])),
  );

  return (
    <div className="max-w-5xl space-y-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Review parsed extract</h1>
          <p className="text-sm text-slate-500">
            From <span className="font-mono">{doc.title}</span>
            {playbook ? <> · Playbook: <strong>{playbook}</strong></> : null}
            {" · "}Confidence: <strong className="capitalize">{confidence}</strong>
          </p>
        </div>
        <Link href="/company/documents" className="text-sm text-blue-600 hover:underline">
          ← back to Documents
        </Link>
      </header>

      {!payload && (
        <section className="card">
          <p className="text-sm">This document hasn&apos;t been parsed yet.</p>
          <form action={parseDocument} className="mt-3 flex items-end gap-3">
            <input type="hidden" name="documentId" value={doc.id} />
            <div>
              <label className="label">Force form (optional)</label>
              <input className="input" name="hintForm" placeholder="e.g. INC-22" />
            </div>
            <button className="btn" type="submit">Run parser</button>
          </form>
        </section>
      )}

      {payload && !matched && (
        <section className="card">
          <p className="text-sm text-amber-700">
            No playbook matched. Re-run with a form hint or add a playbook YAML for this form type.
          </p>
          <form action={parseDocument} className="mt-3 flex items-end gap-3">
            <input type="hidden" name="documentId" value={doc.id} />
            <div>
              <label className="label">Force form</label>
              <input className="input" name="hintForm" placeholder="e.g. INC-22" required />
            </div>
            <button className="btn" type="submit">Re-run</button>
          </form>
        </section>
      )}

      {payload && (
        <section className="card">
          <h2 className="text-sm font-semibold text-slate-700">Source signals</h2>
          <ul className="mt-2 grid grid-cols-2 gap-x-6 text-xs text-slate-500 sm:grid-cols-4">
            <li>Pages: {String(raw.page_count ?? "–")}</li>
            <li>AcroForm fields: {String(raw.acroform_fields_found ?? "–")}</li>
            <li>Tables: {String(raw.tables_found ?? "–")}</li>
            <li>OCR used: {raw.ocr_used ? "yes" : "no"}</li>
          </ul>
          {warnings.length > 0 && (
            <ul className="mt-3 list-disc pl-5 text-xs text-amber-700">
              {warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
          <form action={parseDocument} className="mt-3 flex items-center gap-2">
            <input type="hidden" name="documentId" value={doc.id} />
            <input className="input !py-1 max-w-[10rem]" name="hintForm" placeholder="form hint" />
            <button className="btn-secondary !py-1 text-xs" type="submit">Re-parse</button>
          </form>
        </section>
      )}

      {renderable.map((s) => (
        <SectionCard key={s.key} section={s} extracted={extracted} docId={doc.id} />
      ))}

      {renderable.length === 0 && payload && matched && (
        <section className="card text-center text-sm text-slate-500">
          Playbook matched but no actionable fields were extracted. Check the rules for{" "}
          <strong>{playbook}</strong>.
        </section>
      )}
    </div>
  );
}

function SectionCard({
  section, extracted, docId,
}: { section: Section; extracted: Extract; docId: string }) {
  const cells: Array<{ name: string; slot: FieldSlot }> = [];
  for (const entity of section.entities) {
    const fields = extracted[entity];
    if (!isEntityFields(fields)) continue;
    for (const [fieldName, slot] of Object.entries(fields)) {
      cells.push({ name: `${entity}.${fieldName}`, slot });
    }
  }
  return (
    <section className="card">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{section.label}</h2>
          <p className="text-xs text-slate-500">{section.description}</p>
        </div>
      </header>
      <form action={section.action} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <input type="hidden" name="documentId" value={docId} />
        {cells.map((c) => <FieldCell key={c.name} name={c.name} slot={c.slot} />)}
        <div className="sm:col-span-3 flex items-center gap-3">
          <button className="btn" type="submit">Accept &amp; write to master</button>
          <span className="text-xs text-slate-500">
            Edit any cell before accepting. Source &amp; confidence shown next to each label.
          </span>
        </div>
      </form>
    </section>
  );
}

function FieldCell({ name, slot }: { name: string; slot: FieldSlot }) {
  const v = slot?.value;
  const value = v === null || v === undefined ? "" : String(v);
  const sourceBadge = badgeFor(slot?.source);
  const conf = typeof slot?.confidence === "number" ? Math.round(slot.confidence * 100) : 0;
  const label = prettify(name.split(".").pop() || name);
  return (
    <div>
      <label className="label flex items-center justify-between gap-2">
        <span>{label}</span>
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${sourceBadge}`}>
          {slot?.source ?? "?"} · {conf}%
        </span>
      </label>
      <input className="input" name={name} defaultValue={value} />
    </div>
  );
}

function badgeFor(source: string | undefined): string {
  switch (source) {
    case "acroform": return "bg-emerald-100 text-emerald-800";
    case "regex":    return "bg-blue-100 text-blue-800";
    case "default":  return "bg-slate-100 text-slate-700";
    case "llm":      return "bg-purple-100 text-purple-800";
    case "ocr":      return "bg-amber-100 text-amber-800";
    default:         return "bg-slate-100 text-slate-700";
  }
}

function prettify(name: string): string {
  return name
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (s) => s.toUpperCase())
    .trim();
}

function isEntityFields(v: unknown): v is EntityFields {
  return Boolean(
    v && typeof v === "object" && !Array.isArray(v) &&
    Object.values(v as Record<string, unknown>).every(
      (slot) => slot && typeof slot === "object" && "value" in (slot as object),
    ),
  );
}
