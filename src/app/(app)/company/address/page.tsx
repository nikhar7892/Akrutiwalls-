import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import { addAddress } from "@/app/actions/company";

export const dynamic = "force-dynamic";

const TYPES = ["REGISTERED", "CORPORATE", "CORRESPONDENCE", "FACTORY", "BRANCH"] as const;

export default async function AddressPage() {
  const { company } = await requireActiveCompany();
  const addresses = await prisma.address.findMany({
    where: { companyId: company.id },
    orderBy: [{ effectiveTo: "asc" }, { effectiveFrom: "desc" }],
  });

  return (
    <div className="max-w-4xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Addresses</h1>
        <p className="text-sm text-slate-500">
          Versioned. The row with no “To” date is the current address.
        </p>
      </header>

      <section className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Address</th>
              <th>From</th>
              <th>To</th>
              <th>Change ref</th>
            </tr>
          </thead>
          <tbody>
            {addresses.map((a) => (
              <tr key={a.id}>
                <td>{a.type}</td>
                <td>
                  {a.line1}
                  {a.line2 ? `, ${a.line2}` : ""}, {a.city}, {a.state} {a.pin}
                </td>
                <td>{a.effectiveFrom.toISOString().slice(0, 10)}</td>
                <td>{a.effectiveTo ? a.effectiveTo.toISOString().slice(0, 10) : <span className="text-green-700">current</span>}</td>
                <td>{a.changeFiling ?? "—"}</td>
              </tr>
            ))}
            {addresses.length === 0 && (
              <tr><td colSpan={5} className="text-center text-slate-500">No addresses yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Add / change address</h2>
        <p className="text-xs text-slate-500">
          Adding a new address of the same type will automatically close the existing current one.
        </p>
        <form action={addAddress} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Type</label>
            <select className="input" name="type" defaultValue="REGISTERED">
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Effective from</label>
            <input className="input" type="date" name="effectiveFrom" required />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Line 1</label>
            <input className="input" name="line1" required />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Line 2</label>
            <input className="input" name="line2" />
          </div>
          <div><label className="label">City</label><input className="input" name="city" required /></div>
          <div><label className="label">State</label><input className="input" name="state" required /></div>
          <div><label className="label">PIN</label><input className="input" name="pin" required pattern="\d{6}" /></div>
          <div><label className="label">Country</label><input className="input" name="country" defaultValue="India" /></div>
          <div><label className="label">Email</label><input className="input" type="email" name="email" /></div>
          <div><label className="label">Phone</label><input className="input" name="phone" /></div>
          <div><label className="label">Change filing (INC-22 SRN etc.)</label><input className="input" name="changeFiling" /></div>
          <div className="sm:col-span-2">
            <label className="label">Notes</label>
            <textarea className="input" name="notes" rows={2} />
          </div>
          <div className="sm:col-span-2">
            <button className="btn" type="submit">Save address</button>
          </div>
        </form>
      </section>
    </div>
  );
}
