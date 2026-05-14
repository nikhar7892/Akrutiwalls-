import Link from "next/link";
import { requireActiveCompany } from "@/lib/session";
import { resolveFirm } from "@/lib/firm";

export const dynamic = "force-dynamic";

const NAV = [
  { href: "/dashboard", label: "Overview" },
  { href: "/company/identity", label: "Identity" },
  { href: "/company/address", label: "Address" },
  { href: "/company/capital", label: "Capital" },
  { href: "/company/directors", label: "Directors" },
  { href: "/company/shareholding", label: "Shareholding / Cap Table" },
  { href: "/company/documents", label: "Documents" },
  { href: "/company/filings", label: "MCA Forms & Filings" },
];

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, company, memberships } = await requireActiveCompany();
  const firm = await resolveFirm();
  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white p-4 md:block">
        <div className="flex items-center gap-2 px-2 pb-3">
          {firm.logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={firm.logoUrl} alt="" className="h-6 w-6 rounded object-contain" />
          ) : null}
          <div className="truncate text-sm font-semibold text-slate-900">{firm.productName}</div>
        </div>
        <div className="border-t border-slate-100 px-2 pb-4 pt-3">
          <div className="text-xs uppercase tracking-wide text-slate-400">Workspace</div>
          <div className="mt-1 truncate text-sm font-semibold text-slate-900">{company.name}</div>
          <div className="text-xs text-slate-500">CIN {company.cin}</div>
        </div>
        <nav className="space-y-1">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className="tab-link block">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-8 border-t border-slate-200 pt-4 text-xs text-slate-500">
          <div className="truncate">{user.email}</div>
          <div className="mt-1">Role: {user.role}</div>
          <div className="mt-3 space-y-1">
            {(user.role === "PLATFORM_ADMIN" || user.role === "ADMIN") && (
              <Link href="/admin" className="block text-blue-600 hover:underline">
                Admin
              </Link>
            )}
            {memberships.length > 1 && (
              <Link href="/select-company" className="block text-blue-600 hover:underline">
                Switch company
              </Link>
            )}
            <Link href="/api/auth/signout" className="block text-blue-600 hover:underline">
              Sign out
            </Link>
          </div>
        </div>
      </aside>
      <main className="flex-1 p-6 md:p-8">{children}</main>
    </div>
  );
}
