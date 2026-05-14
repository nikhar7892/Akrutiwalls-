import { redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";
import { createCompany, createUser, grantMembership } from "@/app/actions/admin";

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const user = await requireUser();
  if (user.role !== "ADMIN") redirect("/dashboard");

  const [companies, users] = await Promise.all([
    prisma.company.findMany({ orderBy: { name: "asc" }, include: { memberships: { include: { user: true } } } }),
    prisma.user.findMany({ orderBy: { email: "asc" } }),
  ]);

  return (
    <div className="max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Admin</h1>
        <p className="text-sm text-slate-500">Create companies, users, and grant memberships.</p>
      </header>

      <section className="card">
        <h2 className="text-base font-semibold">Create company</h2>
        <form action={createCompany} className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input className="input sm:col-span-2" name="name" placeholder="Company name" required />
          <input className="input" name="cin" placeholder="CIN" required />
          <button className="btn sm:col-span-3" type="submit">Create company</button>
        </form>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Create user</h2>
        <form action={createUser} className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-4">
          <input className="input" name="email" type="email" placeholder="Email" required />
          <input className="input" name="password" placeholder="Initial password" required />
          <input className="input" name="name" placeholder="Display name" />
          <select className="input" name="role" defaultValue="STAFF">
            <option value="ADMIN">ADMIN</option>
            <option value="STAFF">STAFF</option>
            <option value="CLIENT">CLIENT</option>
          </select>
          <button className="btn sm:col-span-4" type="submit">Create user</button>
        </form>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Grant membership</h2>
        <p className="text-xs text-slate-500">Link a user to a company. A user can belong to multiple companies.</p>
        <form action={grantMembership} className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-4">
          <select className="input" name="userId" required>
            <option value="">Pick user…</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.email} ({u.role})</option>)}
          </select>
          <select className="input" name="companyId" required>
            <option value="">Pick company…</option>
            {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select className="input" name="role" defaultValue="EDITOR">
            <option value="OWNER">OWNER</option>
            <option value="EDITOR">EDITOR</option>
            <option value="VIEWER">VIEWER</option>
          </select>
          <button className="btn" type="submit">Grant</button>
        </form>
      </section>

      <section className="card overflow-x-auto">
        <h2 className="mb-3 text-base font-semibold">Companies &amp; members</h2>
        <table className="table">
          <thead><tr><th>Company</th><th>CIN</th><th>Members</th></tr></thead>
          <tbody>
            {companies.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.cin}</td>
                <td>
                  <ul className="space-y-1">
                    {c.memberships.map((m) => (
                      <li key={m.id} className="text-xs">
                        {m.user.email} — {m.role}
                      </li>
                    ))}
                  </ul>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
