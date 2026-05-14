import Link from "next/link";
import { redirect } from "next/navigation";
import { requireUser } from "@/lib/session";
import { resolveFirm } from "@/lib/firm";

export const dynamic = "force-dynamic";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser();
  if (user.role !== "PLATFORM_ADMIN" && user.role !== "ADMIN") redirect("/dashboard");
  const firm = await resolveFirm();
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {firm.logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={firm.logoUrl} alt="" className="h-8 w-8 rounded object-contain" />
            ) : null}
            <div>
              <div className="text-xs uppercase tracking-wide text-slate-400">{firm.productName}</div>
              <div className="text-sm font-semibold">Platform Admin</div>
            </div>
          </div>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/admin" className="text-blue-600 hover:underline">Overview</Link>
            <Link href="/admin/firms" className="text-blue-600 hover:underline">Firms</Link>
            <Link href="/select-company" className="text-blue-600 hover:underline">Workspaces</Link>
            <Link href="/api/auth/signout" className="text-blue-600 hover:underline">Sign out</Link>
          </nav>
        </div>
      </header>
      <main className="p-6 md:p-8">{children}</main>
    </div>
  );
}
