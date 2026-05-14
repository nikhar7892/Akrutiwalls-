import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import {
  addFiling,
  addFilingAttachment,
  deleteFilingAttachment,
} from "@/app/actions/company";

export const dynamic = "force-dynamic";

const STATUSES = ["PENDING", "FILED", "APPROVED", "REJECTED", "RESUBMITTED"] as const;
const COMMON_FORMS = [
  "INC-22", "DIR-12", "SH-7", "PAS-3", "MGT-14",
  "AOC-4", "MGT-7", "MGT-7A", "DIR-3 KYC", "ADT-1", "INC-20A", "DPT-3",
];

export default async function FilingsPage() {
  const { company } = await requireActiveCompany();
  const filings = await prisma.filing.findMany({
    where: { companyId: company.id },
    include: { attachments: true },
    orderBy: [{ filedOn: "desc" }, { createdAt: "desc" }],
  });

  return (
    <div className="max-w-6xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold">MCA filings &amp; forms</h1>
        <p className="text-sm text-slate-500">
          Log every form filed with SRN, amount paid, purpose. Attach the form PDF and challan
          receipt. Later, uploading a form will auto-fill these fields via the parser.
        </p>
      </header>

      <section className="space-y-4">
        {filings.map((f) => {
          const formAtt = f.attachments.find((a) => a.attachmentRole === "FORM");
          const challanAtt = f.attachments.find((a) => a.attachmentRole === "CHALLAN");
          const others = f.attachments.filter((a) => a.attachmentRole === "OTHER");
          return (
            <article key={f.id} className="card">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-base font-semibold">
                    {f.form}
                    {f.srn ? <span className="ml-2 text-sm font-normal text-slate-500">SRN {f.srn}</span> : null}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {f.filedOn ? `Filed ${f.filedOn.toISOString().slice(0, 10)}` : "Not yet filed"}
                    {f.fy ? ` · FY ${f.fy}` : ""}
                    {" · "}
                    <span className="font-medium">{f.status}</span>
                  </div>
                  {f.purpose && (
                    <div className="mt-2 text-sm text-slate-700">{f.purpose}</div>
                  )}
                </div>
                <div className="text-right text-sm">
                  {f.amountPaid !== null && (
                    <div className="text-base font-semibold">
                      ₹ {Number(f.amountPaid).toLocaleString("en-IN")}
                    </div>
                  )}
                  {f.remarks && <div className="mt-1 text-xs text-slate-500">{f.remarks}</div>}
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <AttachmentSlot filingId={f.id} role="FORM" doc={formAtt ?? null} label="Form PDF" />
                <AttachmentSlot filingId={f.id} role="CHALLAN" doc={challanAtt ?? null} label="Challan receipt" />
              </div>

              {others.length > 0 && (
                <div className="mt-3">
                  <div className="label">Other attachments</div>
                  <ul className="space-y-1 text-sm">
                    {others.map((o) => (
                      <li key={o.id} className="flex items-center justify-between gap-2">
                        <a className="text-blue-600 underline" href={`/api/documents/${o.id}`} target="_blank">
                          {o.title}
                        </a>
                        <form action={deleteFilingAttachment}>
                          <input type="hidden" name="id" value={o.id} />
                          <button className="text-xs text-red-600 hover:underline" type="submit">remove</button>
                        </form>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <form action={addFilingAttachment} className="mt-3 flex flex-wrap items-end gap-2" encType="multipart/form-data">
                <input type="hidden" name="filingId" value={f.id} />
                <div>
                  <label className="label">Add attachment</label>
                  <select className="input !py-1" name="role" defaultValue="OTHER">
                    <option value="FORM">Replace form PDF</option>
                    <option value="CHALLAN">Replace challan</option>
                    <option value="OTHER">Other attachment</option>
                  </select>
                </div>
                <input className="input !py-1" type="file" name="file" required />
                <button className="btn-secondary" type="submit">Upload</button>
              </form>
            </article>
          );
        })}
        {filings.length === 0 && (
          <div className="card text-center text-sm text-slate-500">No filings logged yet.</div>
        )}
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Log a new filing</h2>
        <p className="text-xs text-slate-500">
          Add metadata + (optionally) the form PDF and challan in one shot.
        </p>
        <form action={addFiling} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3" encType="multipart/form-data">
          <div>
            <label className="label">Form number</label>
            <input className="input" name="form" list="common-forms" required placeholder="e.g. INC-22" />
            <datalist id="common-forms">
              {COMMON_FORMS.map((f) => <option key={f} value={f} />)}
            </datalist>
          </div>
          <div><label className="label">SRN</label><input className="input" name="srn" /></div>
          <div><label className="label">Filed on</label><input className="input" type="date" name="filedOn" /></div>

          <div><label className="label">FY</label><input className="input" name="fy" placeholder="2023-24" /></div>
          <div><label className="label">Amount paid (₹)</label><input className="input" type="number" step="0.01" name="amountPaid" /></div>
          <div>
            <label className="label">Status</label>
            <select className="input" name="status" defaultValue="FILED">
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div className="sm:col-span-3">
            <label className="label">Purpose of form</label>
            <textarea className="input" name="purpose" rows={2} placeholder="e.g. Change of registered office within same ROC" />
          </div>

          <div>
            <label className="label">Form PDF</label>
            <input className="input" type="file" name="formFile" />
          </div>
          <div>
            <label className="label">Challan receipt</label>
            <input className="input" type="file" name="challanFile" />
          </div>
          <div className="sm:col-span-3">
            <label className="label">Remarks</label>
            <textarea className="input" name="remarks" rows={2} />
          </div>
          <div className="sm:col-span-3">
            <button className="btn" type="submit">Save filing</button>
          </div>
        </form>
      </section>
    </div>
  );
}

function AttachmentSlot({
  filingId, role, doc, label,
}: {
  filingId: string;
  role: "FORM" | "CHALLAN";
  label: string;
  doc: { id: string; title: string; sizeBytes: number | null; mimeType: string | null } | null;
}) {
  return (
    <div className="rounded-md border border-dashed border-slate-300 p-3">
      <div className="label">{label}</div>
      {doc ? (
        <div className="flex items-center justify-between gap-2 text-sm">
          <a className="text-blue-600 underline" href={`/api/documents/${doc.id}`} target="_blank">
            {doc.title}
          </a>
          <span className="text-xs text-slate-500">
            {doc.sizeBytes ? `${(doc.sizeBytes / 1024).toFixed(1)} KB` : ""}
          </span>
          <form action={deleteFilingAttachment}>
            <input type="hidden" name="id" value={doc.id} />
            <button className="text-xs text-red-600 hover:underline" type="submit">remove</button>
          </form>
        </div>
      ) : (
        <form action={addFilingAttachment} className="flex items-center gap-2" encType="multipart/form-data">
          <input type="hidden" name="filingId" value={filingId} />
          <input type="hidden" name="role" value={role} />
          <input className="input !py-1 text-xs" type="file" name="file" required />
          <button className="btn-secondary !py-1 text-xs" type="submit">Upload</button>
        </form>
      )}
    </div>
  );
}
