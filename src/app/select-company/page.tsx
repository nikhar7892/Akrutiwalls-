import Link from "next/link";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/session";
import { setActiveCompany } from "../actions/active-company";

export const dynamic = "force-dynamic";

export default async function SelectCompanyPage() {
  const user = await requireUser();
  const memberships = await prisma.membership.findMany({
    where: { userId: user.id },
    include: { company: true },
    orderBy: { createdAt: "asc" },
  });

  if (memberships.length === 0) redirect("/no-access");
  if (memberships.length === 1) {
    await setActiveCompany(memberships[0].companyId);
    redirect("/dashboard");
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-xl font-semibold">Select a company</h1>
      <p className="mt-1 text-sm text-slate-500">
        You have access to {memberships.length} companies. Pick one to enter its workspace. To switch later,
        sign out and select another.
      </p>
      <ul className="mt-6 space-y-3">
        {memberships.map((m) => (
          <li key={m.id} className="card flex items-center justify-between">
            <div>
              <div className="text-base font-medium">{m.company.name}</div>
              <div className="text-xs text-slate-500">
                CIN {m.company.cin} · {m.role}
              </div>
            </div>
            <form action={selectAndGo.bind(null, m.companyId)}>
              <button className="btn">Enter</button>
            </form>
          </li>
        ))}
      </ul>
      <div className="mt-8">
        <Link href="/api/auth/signout" className="text-sm text-slate-500 underline">
          Sign out
        </Link>
      </div>
    </main>
  );
}

async function selectAndGo(companyId: string) {
  "use server";
  await setActiveCompany(companyId);
  redirect("/dashboard");
}
