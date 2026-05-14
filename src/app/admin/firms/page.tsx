import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { createFirm } from "@/app/actions/firms";

export const dynamic = "force-dynamic";

export default async function FirmsPage() {
  const firms = await prisma.firm.findMany({
    orderBy: [{ isDefault: "desc" }, { name: "asc" }],
    include: { _count: { select: { companies: true, users: true } } },
  });

  return (
    <div className="max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Firms</h1>
        <p className="text-sm text-slate-500">
          Each Firm is one CA/CS practice using the platform — its own brand, its own custom domain,
          its own staff and client companies.
        </p>
      </header>

      <section className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr><th>Firm</th><th>Domain</th><th>Brand</th><th>Companies</th><th>Users</th><th></th></tr>
          </thead>
          <tbody>
            {firms.map((f) => (
              <tr key={f.id}>
                <td>
                  <div className="font-medium">
                    {f.productName}
                    {f.isDefault && (
                      <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                        default
                      </span>
                    )}
                    {!f.isActive && (
                      <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">
                        inactive
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500">/{f.slug}</div>
                </td>
                <td className="text-xs">{f.customDomain ?? "—"}</td>
                <td>
                  <span className="inline-block h-4 w-4 rounded" style={{ backgroundColor: f.primaryColor }} />
                  <span className="ml-2 inline-block h-4 w-4 rounded" style={{ backgroundColor: f.accentColor }} />
                </td>
                <td>{f._count.companies}</td>
                <td>{f._count.users}</td>
                <td>
                  <Link className="text-blue-600 underline" href={`/admin/firms/${f.id}`}>edit</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Create firm</h2>
        <p className="text-xs text-slate-500">
          The slug is internal; the product name + logo + colours are what the firm&apos;s users see.
        </p>
        <form action={createFirm} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div><label className="label">Slug</label><input className="input" name="slug" required placeholder="acme-ca" /></div>
          <div><label className="label">Internal name</label><input className="input" name="name" required placeholder="Acme &amp; Associates" /></div>
          <div><label className="label">Product name (user-facing)</label><input className="input" name="productName" required placeholder="Acme MCA Portal" /></div>
          <div><label className="label">Custom domain</label><input className="input" name="customDomain" placeholder="mca.acmeca.in" /></div>
          <div><label className="label">Primary colour</label><input className="input" type="color" name="primaryColor" defaultValue="#1f2937" /></div>
          <div><label className="label">Accent colour</label><input className="input" type="color" name="accentColor" defaultValue="#2563eb" /></div>
          <div><label className="label">Support email</label><input className="input" type="email" name="supportEmail" /></div>
          <div className="sm:col-span-2"><label className="label">Footer text</label><input className="input" name="footerText" placeholder="© 2026 Acme &amp; Associates" /></div>
          <div className="sm:col-span-3"><button className="btn" type="submit">Create firm</button></div>
        </form>
      </section>
    </div>
  );
}
