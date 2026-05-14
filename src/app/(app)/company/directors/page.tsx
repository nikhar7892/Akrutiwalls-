import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";
import { addDirectorship, endDirectorship } from "@/app/actions/company";

export const dynamic = "force-dynamic";

const DESIGNATIONS = [
  "DIRECTOR", "MANAGING_DIRECTOR", "WHOLE_TIME_DIRECTOR", "INDEPENDENT_DIRECTOR",
  "NOMINEE_DIRECTOR", "ADDITIONAL_DIRECTOR", "ALTERNATE_DIRECTOR",
  "CHAIRMAN", "CFO", "CS", "CEO",
] as const;

export default async function DirectorsPage() {
  const { company } = await requireActiveCompany();
  const directorships = await prisma.directorship.findMany({
    where: { companyId: company.id },
    include: { director: true },
    orderBy: [{ cessationDate: "asc" }, { appointmentDate: "desc" }],
  });

  const current = directorships.filter((d) => !d.cessationDate);
  const past = directorships.filter((d) => d.cessationDate);

  return (
    <div className="max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Directors &amp; KMP</h1>
        <p className="text-sm text-slate-500">Current directors plus full appointment history.</p>
      </header>

      <section className="card overflow-x-auto">
        <h2 className="mb-3 text-base font-semibold">Current</h2>
        <table className="table">
          <thead>
            <tr><th>DIN</th><th>Name</th><th>Designation</th><th>Appointed</th><th>PAN</th><th>Mode</th><th>End</th></tr>
          </thead>
          <tbody>
            {current.map((d) => (
              <tr key={d.id}>
                <td>{d.director.din}</td>
                <td>{d.director.name}</td>
                <td>{d.designation}</td>
                <td>{d.appointmentDate.toISOString().slice(0, 10)}</td>
                <td>{d.director.pan ?? "—"}</td>
                <td>{d.appointmentMode ?? "—"}</td>
                <td>
                  <form action={endDirectorship} className="flex items-center gap-2">
                    <input type="hidden" name="id" value={d.id} />
                    <input className="input !py-1" type="date" name="cessationDate" required />
                    <input className="input !py-1" name="cessationMode" placeholder="DIR-12 SRN" />
                    <button className="btn-secondary !py-1" type="submit">End</button>
                  </form>
                </td>
              </tr>
            ))}
            {current.length === 0 && (
              <tr><td colSpan={7} className="text-center text-slate-500">No current directors.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="card overflow-x-auto">
        <h2 className="mb-3 text-base font-semibold">Past directors</h2>
        <table className="table">
          <thead>
            <tr><th>DIN</th><th>Name</th><th>Designation</th><th>Appointed</th><th>Ceased</th><th>Mode</th></tr>
          </thead>
          <tbody>
            {past.map((d) => (
              <tr key={d.id}>
                <td>{d.director.din}</td>
                <td>{d.director.name}</td>
                <td>{d.designation}</td>
                <td>{d.appointmentDate.toISOString().slice(0, 10)}</td>
                <td>{d.cessationDate?.toISOString().slice(0, 10)}</td>
                <td>{d.cessationMode ?? "—"}</td>
              </tr>
            ))}
            {past.length === 0 && (
              <tr><td colSpan={6} className="text-center text-slate-500">No past directors recorded.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Add director / appointment</h2>
        <form action={addDirectorship} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div><label className="label">DIN</label><input className="input" name="din" required pattern="\d{8}" /></div>
          <div className="sm:col-span-2"><label className="label">Name</label><input className="input" name="name" required /></div>
          <div><label className="label">PAN</label><input className="input" name="pan" /></div>
          <div><label className="label">DOB</label><input className="input" type="date" name="dob" /></div>
          <div><label className="label">Nationality</label><input className="input" name="nationality" defaultValue="Indian" /></div>
          <div><label className="label">Email</label><input className="input" type="email" name="email" /></div>
          <div><label className="label">Phone</label><input className="input" name="phone" /></div>
          <div className="sm:col-span-3"><label className="label">Address</label><textarea className="input" name="address" rows={2} /></div>
          <div>
            <label className="label">Designation</label>
            <select className="input" name="designation" defaultValue="DIRECTOR">
              {DESIGNATIONS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div><label className="label">Appointment date</label><input className="input" type="date" name="appointmentDate" required /></div>
          <div><label className="label">Appointment mode (DIR-12 SRN)</label><input className="input" name="appointmentMode" /></div>
          <div className="sm:col-span-3"><button className="btn" type="submit">Add directorship</button></div>
        </form>
      </section>
    </div>
  );
}
