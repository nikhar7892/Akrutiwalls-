import Link from "next/link";
import { redirect } from "next/navigation";
import { requireUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser();
  if (user.role !== "ADMIN") redirect("/dashboard");
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-400">Akrutiwalls MCA</div>
            <div className="text-sm font-semibold">Admin</div>
          </div>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/select-company" className="text-blue-600 hover:underline">Workspaces</Link>
            <Link href="/api/auth/signout" className="text-blue-600 hover:underline">Sign out</Link>
          </nav>
        </div>
      </header>
      <main className="p-6 md:p-8">{children}</main>
    </div>
  );
}
