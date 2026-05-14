import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import { addCapitalChange } from "@/app/actions/company";

export const dynamic = "force-dynamic";

const REASONS = [
  "INITIAL", "ALLOTMENT", "BUYBACK", "BONUS", "SPLIT",
  "CONSOLIDATION", "REDUCTION", "CONVERSION", "OTHER",
] as const;

export default async function CapitalPage() {
  const { company } = await requireActiveCompany();
  const history = await prisma.capitalHistory.findMany({
    where: { companyId: company.id },
    orderBy: { effectiveFrom: "desc" },
  });

  const fmt = (n: number) => n.toLocaleString("en-IN");

  return (
    <div className="max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Capital structure</h1>
        <p className="text-sm text-slate-500">
          Each row is a point-in-time capital snapshot. New entries automatically close the prior one.
        </p>
      </header>

      <section className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Effective</th>
              <th>Authorized</th>
              <th>Paid-up</th>
              <th>Face value</th>
              <th>Authorized shares</th>
              <th>Paid-up shares</th>
              <th>Reason</th>
              <th>Filing</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.id}>
                <td>
                  {h.effectiveFrom.toISOString().slice(0, 10)}
                  {" → "}
                  {h.effectiveTo ? h.effectiveTo.toISOString().slice(0, 10) : <span className="text-green-700">current</span>}
                </td>
                <td>₹ {fmt(Number(h.authorizedAmount))}</td>
                <td>₹ {fmt(Number(h.paidUpAmount))}</td>
                <td>₹ {fmt(Number(h.faceValue))}</td>
                <td>{h.authorizedShares.toString()}</td>
                <td>{h.paidUpShares.toString()}</td>
                <td>{h.changeReason}</td>
                <td>{h.changeFiling ?? "—"}</td>
              </tr>
            ))}
            {history.length === 0 && (
              <tr><td colSpan={8} className="text-center text-slate-500">No capital history yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Record capital change</h2>
        <form action={addCapitalChange} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div><label className="label">Effective from</label><input className="input" type="date" name="effectiveFrom" required /></div>
          <div><label className="label">Reason</label>
            <select className="input" name="changeReason" defaultValue="ALLOTMENT">
              {REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div><label className="label">Filing ref (SH-7 / PAS-3 SRN)</label><input className="input" name="changeFiling" /></div>
          <div><label className="label">Authorized capital (₹)</label><input className="input" type="number" step="0.01" name="authorizedAmount" required /></div>
          <div><label className="label">Paid-up capital (₹)</label><input className="input" type="number" step="0.01" name="paidUpAmount" required /></div>
          <div><label className="label">Face value (₹/share)</label><input className="input" type="number" step="0.01" name="faceValue" required /></div>
          <div><label className="label">Authorized shares</label><input className="input" type="number" name="authorizedShares" required /></div>
          <div><label className="label">Paid-up shares</label><input className="input" type="number" name="paidUpShares" required /></div>
          <div className="sm:col-span-3">
            <label className="label">Notes</label><textarea className="input" name="notes" rows={2} />
          </div>
          <div className="sm:col-span-3">
            <button className="btn" type="submit">Save capital entry</button>
          </div>
        </form>
      </section>
    </div>
  );
}
