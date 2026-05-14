import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import { addFiling } from "@/app/actions/company";

export const dynamic = "force-dynamic";

const STATUSES = ["PENDING", "FILED", "APPROVED", "REJECTED", "RESUBMITTED"] as const;
const COMMON_FORMS = ["INC-22", "DIR-12", "SH-7", "PAS-3", "MGT-14", "AOC-4", "MGT-7", "MGT-7A", "DIR-3 KYC"];

export default async function FilingsPage() {
  const { company } = await requireActiveCompany();
  const filings = await prisma.filing.findMany({
    where: { companyId: company.id },
    orderBy: [{ filedOn: "desc" }, { createdAt: "desc" }],
  });

  return (
    <div className="max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Filings</h1>
        <p className="text-sm text-slate-500">Log of ROC filings with SRN and status.</p>
      </header>

      <section className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr><th>Form</th><th>SRN</th><th>FY</th><th>Filed on</th><th>Status</th><th>Remarks</th></tr>
          </thead>
          <tbody>
            {filings.map((f) => (
              <tr key={f.id}>
                <td>{f.form}</td>
                <td>{f.srn ?? "—"}</td>
                <td>{f.fy ?? "—"}</td>
                <td>{f.filedOn ? f.filedOn.toISOString().slice(0, 10) : "—"}</td>
                <td>{f.status}</td>
                <td>{f.remarks ?? "—"}</td>
              </tr>
            ))}
            {filings.length === 0 && (
              <tr><td colSpan={6} className="text-center text-slate-500">No filings yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Log a filing</h2>
        <form action={addFiling} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="label">Form</label>
            <input className="input" name="form" list="common-forms" required />
            <datalist id="common-forms">
              {COMMON_FORMS.map((f) => <option key={f} value={f} />)}
            </datalist>
          </div>
          <div><label className="label">SRN</label><input className="input" name="srn" /></div>
          <div><label className="label">FY</label><input className="input" name="fy" placeholder="2023-24" /></div>
          <div><label className="label">Filed on</label><input className="input" type="date" name="filedOn" /></div>
          <div>
            <label className="label">Status</label>
            <select className="input" name="status" defaultValue="PENDING">
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="sm:col-span-3"><label className="label">Remarks</label><textarea className="input" name="remarks" rows={2} /></div>
          <div className="sm:col-span-3"><button className="btn" type="submit">Save filing</button></div>
        </form>
      </section>
    </div>
  );
}
