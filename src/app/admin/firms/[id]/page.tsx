import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/prisma";
import {
  moveCompanyToFirm,
  moveUserToFirm,
  setDevFirmOverride,
  updateFirm,
} from "@/app/actions/firms";

export const dynamic = "force-dynamic";

export default async function FirmEditPage({ params }: { params: { id: string } }) {
  const firm = await prisma.firm.findUnique({
    where: { id: params.id },
    include: {
      companies: { orderBy: { name: "asc" } },
      users: { orderBy: { email: "asc" } },
    },
  });
  if (!firm) notFound();

  const [allCompanies, allUsers, allFirms] = await Promise.all([
    prisma.company.findMany({ orderBy: { name: "asc" } }),
    prisma.user.findMany({ orderBy: { email: "asc" } }),
    prisma.firm.findMany({ orderBy: { name: "asc" } }),
  ]);

  return (
    <div className="max-w-5xl space-y-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{firm.productName}</h1>
          <p className="text-sm text-slate-500">
            Firm settings, branding, and tenancy.
          </p>
        </div>
        <Link href="/admin/firms" className="text-sm text-blue-600 hover:underline">
          ← back to firms
        </Link>
      </header>

      <section className="card">
        <h2 className="text-base font-semibold">Brand &amp; domain</h2>
        <form action={updateFirm} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <input type="hidden" name="id" value={firm.id} />
          <div><label className="label">Slug</label><input className="input" name="slug" defaultValue={firm.slug} /></div>
          <div><label className="label">Internal name</label><input className="input" name="name" defaultValue={firm.name} /></div>
          <div><label className="label">Product name (user-facing)</label><input className="input" name="productName" defaultValue={firm.productName} /></div>
          <div><label className="label">Custom domain</label><input className="input" name="customDomain" defaultValue={firm.customDomain ?? ""} placeholder="mca.acmeca.in" /></div>
          <div><label className="label">Primary colour</label><input className="input" type="color" name="primaryColor" defaultValue={firm.primaryColor} /></div>
          <div><label className="label">Accent colour</label><input className="input" type="color" name="accentColor" defaultValue={firm.accentColor} /></div>
          <div><label className="label">Logo URL</label><input className="input" name="logoUrl" defaultValue={firm.logoUrl ?? ""} placeholder="https://…/logo.png" /></div>
          <div><label className="label">Favicon URL</label><input className="input" name="faviconUrl" defaultValue={firm.faviconUrl ?? ""} /></div>
          <div><label className="label">Support email</label><input className="input" type="email" name="supportEmail" defaultValue={firm.supportEmail ?? ""} /></div>
          <div className="sm:col-span-2"><label className="label">Footer text</label><input className="input" name="footerText" defaultValue={firm.footerText ?? ""} /></div>
          <div>
            <label className="label flex items-center gap-2">
              <input type="checkbox" name="isActive" defaultChecked={firm.isActive} />
              <span>Active</span>
            </label>
          </div>
          <div className="sm:col-span-3"><button className="btn" type="submit">Save</button></div>
        </form>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Preview this firm locally</h2>
        <p className="text-xs text-slate-500">
          Sets a cookie so the current browser renders as if it hit this firm&apos;s domain.
          Useful before the real DNS / TLS is wired up.
        </p>
        <form action={setDevFirmOverride} className="mt-3 flex items-center gap-2">
          <input type="hidden" name="slug" value={firm.slug} />
          <button className="btn-secondary" type="submit">Preview as {firm.productName}</button>
        </form>
      </section>

      <section className="card overflow-x-auto">
        <h2 className="mb-3 text-base font-semibold">Companies in this firm ({firm.companies.length})</h2>
        <table className="table">
          <thead><tr><th>Company</th><th>CIN</th><th>Move to another firm</th></tr></thead>
          <tbody>
            {firm.companies.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td className="text-xs">{c.cin}</td>
                <td>
                  <form action={moveCompanyToFirm} className="flex items-center gap-2">
                    <input type="hidden" name="companyId" value={c.id} />
                    <select className="input !py-1 text-xs" name="firmId" defaultValue={firm.id}>
                      {allFirms.map((f) => (
                        <option key={f.id} value={f.id}>{f.productName}</option>
                      ))}
                    </select>
                    <button className="btn-secondary !py-1 text-xs" type="submit">Move</button>
                  </form>
                </td>
              </tr>
            ))}
            {firm.companies.length === 0 && (
              <tr><td colSpan={3} className="text-center text-slate-500">No companies in this firm yet.</td></tr>
            )}
          </tbody>
        </table>
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase text-slate-500">Pull a company in</h3>
          <form action={moveCompanyToFirm} className="mt-2 flex items-center gap-2">
            <input type="hidden" name="firmId" value={firm.id} />
            <select className="input !py-1 text-xs" name="companyId" required>
              <option value="">Choose a company…</option>
              {allCompanies
                .filter((c) => c.firmId !== firm.id)
                .map((c) => (
                  <option key={c.id} value={c.id}>{c.name} ({c.cin})</option>
                ))}
            </select>
            <button className="btn-secondary !py-1 text-xs" type="submit">Attach</button>
          </form>
        </div>
      </section>

      <section className="card overflow-x-auto">
        <h2 className="mb-3 text-base font-semibold">Staff in this firm ({firm.users.length})</h2>
        <table className="table">
          <thead><tr><th>Email</th><th>Role</th><th>Move</th></tr></thead>
          <tbody>
            {firm.users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.role}</td>
                <td>
                  <form action={moveUserToFirm} className="flex items-center gap-2">
                    <input type="hidden" name="userId" value={u.id} />
                    <select className="input !py-1 text-xs" name="firmId" defaultValue={firm.id}>
                      {allFirms.map((f) => (
                        <option key={f.id} value={f.id}>{f.productName}</option>
                      ))}
                    </select>
                    <button className="btn-secondary !py-1 text-xs" type="submit">Move</button>
                  </form>
                </td>
              </tr>
            ))}
            {firm.users.length === 0 && (
              <tr><td colSpan={3} className="text-center text-slate-500">No users in this firm yet.</td></tr>
            )}
          </tbody>
        </table>
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase text-slate-500">Pull a user in</h3>
          <form action={moveUserToFirm} className="mt-2 flex items-center gap-2">
            <input type="hidden" name="firmId" value={firm.id} />
            <select className="input !py-1 text-xs" name="userId" required>
              <option value="">Choose a user…</option>
              {allUsers
                .filter((u) => u.firmId !== firm.id)
                .map((u) => (
                  <option key={u.id} value={u.id}>{u.email} ({u.role})</option>
                ))}
            </select>
            <button className="btn-secondary !py-1 text-xs" type="submit">Attach</button>
          </form>
        </div>
      </section>
    </div>
  );
}
