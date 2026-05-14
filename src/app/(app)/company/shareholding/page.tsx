import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import { addShareholdingEntry } from "@/app/actions/company";

export const dynamic = "force-dynamic";

const TYPES = [
  "INDIVIDUAL", "BODY_CORPORATE", "HUF", "FOREIGN_INDIVIDUAL",
  "FOREIGN_CORPORATE", "TRUST", "GOVERNMENT",
] as const;
const CLASSES = ["EQUITY", "PREFERENCE", "CCPS", "OCPS"] as const;
const TXN = [
  "ALLOTMENT", "TRANSFER_IN", "TRANSFER_OUT", "BUYBACK",
  "BONUS", "SPLIT", "CONVERSION", "OPENING_BALANCE",
] as const;

function isInflow(t: string) {
  return ["ALLOTMENT", "TRANSFER_IN", "BONUS", "SPLIT", "CONVERSION", "OPENING_BALANCE"].includes(t);
}

export default async function ShareholdingPage({
  searchParams,
}: { searchParams: { asOf?: string } }) {
  const { company } = await requireActiveCompany();
  const asOf = searchParams.asOf ? new Date(searchParams.asOf) : new Date();

  const [entries, shareholders] = await Promise.all([
    prisma.shareholdingEntry.findMany({
      where: { companyId: company.id, asOfDate: { lte: asOf } },
      include: { shareholder: true },
      orderBy: { asOfDate: "asc" },
    }),
    prisma.shareholder.findMany({
      where: { companyId: company.id },
      orderBy: { name: "asc" },
    }),
  ]);

  // Build cap table: (shareholderId|shareClass) -> running net shares
  const capTable = new Map<string, { name: string; type: string; shareClass: string; shares: bigint }>();
  for (const e of entries) {
    const key = `${e.shareholderId}|${e.shareClass}`;
    const signed = isInflow(e.transactionType) ? e.numberOfShares : -e.numberOfShares;
    const existing = capTable.get(key);
    capTable.set(key, {
      name: e.shareholder.name,
      type: e.shareholder.type,
      shareClass: e.shareClass,
      shares: (existing?.shares ?? 0n) + signed,
    });
  }
  const capRows = Array.from(capTable.values()).filter((r) => r.shares !== 0n);
  const totalShares = capRows.reduce((acc, r) => acc + r.shares, 0n);

  // Recent ledger entries (history) — show last 20 newest first
  const recent = [...entries].reverse().slice(0, 20);

  return (
    <div className="max-w-6xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Shareholding &amp; cap table</h1>
        <p className="text-sm text-slate-500">
          Append-only ledger of share movements. The cap table is computed up to the date below.
        </p>
      </header>

      <section className="card">
        <form className="flex items-end gap-3" action="">
          <div>
            <label className="label">Cap table as of</label>
            <input className="input" type="date" name="asOf" defaultValue={asOf.toISOString().slice(0, 10)} />
          </div>
          <button className="btn-secondary" type="submit">Recompute</button>
        </form>

        <div className="mt-4 overflow-x-auto">
          <table className="table">
            <thead>
              <tr><th>Shareholder</th><th>Type</th><th>Class</th><th>Shares</th><th>% (within class)</th></tr>
            </thead>
            <tbody>
              {capRows.map((r, i) => {
                const classTotal = capRows
                  .filter((x) => x.shareClass === r.shareClass)
                  .reduce((a, x) => a + x.shares, 0n);
                const pct = classTotal === 0n ? 0 : (Number(r.shares) * 100) / Number(classTotal);
                return (
                  <tr key={i}>
                    <td>{r.name}</td>
                    <td>{r.type}</td>
                    <td>{r.shareClass}</td>
                    <td>{r.shares.toString()}</td>
                    <td>{pct.toFixed(2)}%</td>
                  </tr>
                );
              })}
              {capRows.length === 0 && (
                <tr><td colSpan={5} className="text-center text-slate-500">No shareholding yet.</td></tr>
              )}
            </tbody>
            {capRows.length > 0 && (
              <tfoot>
                <tr className="font-semibold">
                  <td colSpan={3}>Total</td>
                  <td>{totalShares.toString()}</td>
                  <td></td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </section>

      <section className="card overflow-x-auto">
        <h2 className="mb-3 text-base font-semibold">Recent ledger entries</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Date</th><th>Shareholder</th><th>Class</th><th>Transaction</th>
              <th>Shares</th><th>Face value</th><th>Premium</th><th>Filing</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((e) => (
              <tr key={e.id}>
                <td>{e.asOfDate.toISOString().slice(0, 10)}</td>
                <td>{e.shareholder.name}</td>
                <td>{e.shareClass}</td>
                <td>{isInflow(e.transactionType) ? "+" : "-"}{e.transactionType}</td>
                <td>{e.numberOfShares.toString()}</td>
                <td>₹ {Number(e.faceValue).toLocaleString("en-IN")}</td>
                <td>{e.premium ? `₹ ${Number(e.premium).toLocaleString("en-IN")}` : "—"}</td>
                <td>{e.filingReference ?? "—"}</td>
              </tr>
            ))}
            {recent.length === 0 && (
              <tr><td colSpan={8} className="text-center text-slate-500">No entries yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Record a share movement</h2>
        <p className="text-xs text-slate-500">
          Existing shareholders are matched on PAN or folio; new ones are auto-created.
        </p>
        <form action={addShareholdingEntry} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <label className="label">Shareholder name</label>
            <input className="input" name="shareholderName" required list="shareholders" />
            <datalist id="shareholders">
              {shareholders.map((s) => <option key={s.id} value={s.name} />)}
            </datalist>
          </div>
          <div>
            <label className="label">Type</label>
            <select className="input" name="type" defaultValue="INDIVIDUAL">
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div><label className="label">PAN</label><input className="input" name="pan" /></div>
          <div><label className="label">Folio</label><input className="input" name="folio" /></div>
          <div>
            <label className="label">Share class</label>
            <select className="input" name="shareClass" defaultValue="EQUITY">
              {CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Transaction</label>
            <select className="input" name="transactionType" defaultValue="ALLOTMENT">
              {TXN.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div><label className="label">Number of shares</label><input className="input" type="number" name="numberOfShares" required /></div>
          <div><label className="label">Face value</label><input className="input" type="number" step="0.01" name="faceValue" required /></div>
          <div><label className="label">Premium / share</label><input className="input" type="number" step="0.01" name="premium" /></div>
          <div><label className="label">As of date</label><input className="input" type="date" name="asOfDate" required /></div>
          <div><label className="label">Filing reference</label><input className="input" name="filingReference" placeholder="PAS-3 / SH-4 SRN" /></div>
          <div className="sm:col-span-3"><label className="label">Notes</label><textarea className="input" name="notes" rows={2} /></div>
          <div className="sm:col-span-3"><button className="btn" type="submit">Add entry</button></div>
        </form>
      </section>
    </div>
  );
}
