import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import { uploadDocument } from "@/app/actions/documents";

export const dynamic = "force-dynamic";

const MASTER_TYPES = [
  "CIN_CERTIFICATE", "MOA", "AOA", "PAN_CARD", "TAN_CERTIFICATE",
  "GST_CERTIFICATE", "COMMON_SEAL", "REGISTERED_OFFICE_PROOF", "BOARD_RESOLUTION",
];
const YEARLY_TYPES = [
  "ITR", "FINANCIALS_AUDITED", "FINANCIALS_PROVISIONAL",
  "AOC_4", "MGT_7", "MGT_7A", "DIR_3_KYC",
  "BOARD_REPORT", "AGM_MINUTES", "SIGNIFICANT_NOTES", "AUDITORS_REPORT",
];
const FILING_TYPES = ["FORM_INC_22", "FORM_DIR_12", "FORM_SH_7", "FORM_PAS_3", "FORM_MGT_14", "CHALLAN"];

export default async function DocumentsPage() {
  const { company } = await requireActiveCompany();
  const docs = await prisma.document.findMany({
    where: { companyId: company.id },
    include: { uploadedBy: true },
    orderBy: { createdAt: "desc" },
  });

  const master = docs.filter((d) => d.category === "MASTER");
  const yearly = docs.filter((d) => d.category === "YEARLY");
  const filing = docs.filter((d) => d.category === "FILING");
  const other = docs.filter((d) => d.category === "OTHER");

  return (
    <div className="max-w-6xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Documents</h1>
        <p className="text-sm text-slate-500">
          Master = forever (MOA, AOA, CIN…). Yearly = FY-tagged (ITR, financials, AOC-4, MGT-7…).
        </p>
      </header>

      <DocSection title="Master documents" docs={master} />
      <DocSection title="Year-wise documents" docs={yearly} showFy />
      <DocSection title="Filing attachments" docs={filing} />
      {other.length > 0 && <DocSection title="Other" docs={other} />}

      <section className="card">
        <h2 className="text-base font-semibold">Upload a document</h2>
        <form action={uploadDocument} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3" encType="multipart/form-data">
          <div>
            <label className="label">Category</label>
            <select className="input" name="category" defaultValue="MASTER" id="doc-category">
              <option value="MASTER">Master</option>
              <option value="YEARLY">Yearly</option>
              <option value="FILING">Filing</option>
              <option value="OTHER">Other</option>
            </select>
          </div>
          <div>
            <label className="label">Document type</label>
            <select className="input" name="docType" defaultValue="MOA">
              <optgroup label="Master">
                {MASTER_TYPES.map((t) => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}
              </optgroup>
              <optgroup label="Yearly">
                {YEARLY_TYPES.map((t) => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}
              </optgroup>
              <optgroup label="Filing">
                {FILING_TYPES.map((t) => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}
              </optgroup>
              <option value="OTHER">OTHER</option>
            </select>
          </div>
          <div>
            <label className="label">FY (for yearly docs)</label>
            <input className="input" name="fy" placeholder="2023-24" />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Title</label>
            <input className="input" name="title" required />
          </div>
          <div>
            <label className="label">File</label>
            <input className="input" type="file" name="file" required />
          </div>
          <div className="sm:col-span-3">
            <label className="label">Notes</label>
            <textarea className="input" name="notes" rows={2} />
          </div>
          <div className="sm:col-span-3">
            <button className="btn" type="submit">Upload</button>
          </div>
        </form>
      </section>
    </div>
  );
}

function DocSection({
  title, docs, showFy,
}: {
  title: string;
  showFy?: boolean;
  docs: Array<{ id: string; title: string; docType: string; fy: string | null; sizeBytes: number | null; mimeType: string | null; createdAt: Date; uploadedBy: { email: string } }>;
}) {
  if (docs.length === 0) return null;
  return (
    <section className="card overflow-x-auto">
      <h2 className="mb-3 text-base font-semibold">{title}</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Title</th><th>Type</th>{showFy && <th>FY</th>}<th>Size</th><th>Uploaded</th><th></th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}>
              <td>{d.title}</td>
              <td>{d.docType.replaceAll("_", " ")}</td>
              {showFy && <td>{d.fy ?? "—"}</td>}
              <td>{d.sizeBytes ? `${(d.sizeBytes / 1024).toFixed(1)} KB` : "—"}</td>
              <td>
                {d.createdAt.toISOString().slice(0, 10)}
                <div className="text-xs text-slate-400">{d.uploadedBy.email}</div>
              </td>
              <td>
                <a className="text-blue-600 underline" href={`/api/documents/${d.id}`} target="_blank">Open</a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
