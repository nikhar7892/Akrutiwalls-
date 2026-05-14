import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { requireActiveCompany } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const { company } = await requireActiveCompany();

  const [directorsCount, currentCapital, currentAddress, docsCount, filingsCount] = await Promise.all([
    prisma.directorship.count({ where: { companyId: company.id, cessationDate: null } }),
    prisma.capitalHistory.findFirst({
      where: { companyId: company.id, effectiveTo: null },
      orderBy: { effectiveFrom: "desc" },
    }),
    prisma.address.findFirst({
      where: { companyId: company.id, type: "REGISTERED", effectiveTo: null },
      orderBy: { effectiveFrom: "desc" },
    }),
    prisma.document.count({ where: { companyId: company.id } }),
    prisma.filing.count({ where: { companyId: company.id } }),
  ]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">{company.name}</h1>
        <p className="text-sm text-slate-500">
          {company.companyClass} · {company.status} · CIN {company.cin}
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Tile title="Active directors" value={String(directorsCount)} href="/company/directors" />
        <Tile
          title="Paid-up capital"
          value={
            currentCapital
              ? `₹ ${Number(currentCapital.paidUpAmount).toLocaleString("en-IN")}`
              : "Not set"
          }
          href="/company/capital"
        />
        <Tile
          title="Registered office"
          value={currentAddress ? `${currentAddress.city}, ${currentAddress.state}` : "Not set"}
          href="/company/address"
        />
        <Tile title="Documents on file" value={String(docsCount)} href="/company/documents" />
        <Tile title="Filings logged" value={String(filingsCount)} href="/company/filings" />
      </section>

      <section className="card">
        <h2 className="text-base font-semibold">Quick start</h2>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-700">
          <li>
            Fill <Link className="text-blue-600 underline" href="/company/identity">Identity</Link> and{" "}
            <Link className="text-blue-600 underline" href="/company/address">Address</Link>.
          </li>
          <li>
            Add <Link className="text-blue-600 underline" href="/company/capital">Capital</Link> (current
            authorized + paid-up).
          </li>
          <li>
            Add <Link className="text-blue-600 underline" href="/company/directors">Directors</Link> with
            DINs.
          </li>
          <li>
            Record <Link className="text-blue-600 underline" href="/company/shareholding">Shareholding</Link>{" "}
            entries (allotments, transfers).
          </li>
          <li>
            Upload <Link className="text-blue-600 underline" href="/company/documents">Documents</Link>{" "}
            (MOA/AOA + year-wise ITR/financials).
          </li>
        </ol>
      </section>
    </div>
  );
}

function Tile({ title, value, href }: { title: string; value: string; href: string }) {
  return (
    <Link href={href} className="card hover:border-brand-accent">
      <div className="text-xs uppercase tracking-wide text-slate-500">{title}</div>
      <div className="mt-2 text-xl font-semibold">{value}</div>
    </Link>
  );
}
