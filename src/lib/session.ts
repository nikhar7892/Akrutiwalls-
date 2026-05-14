import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export const ACTIVE_COMPANY_COOKIE = "akr_active_company";

export type SessionUser = {
  id: string;
  email: string;
  name?: string | null;
  role: "ADMIN" | "STAFF" | "CLIENT";
};

export async function requireUser(): Promise<SessionUser> {
  const session = await getServerSession(authOptions);
  if (!session?.user || !(session.user as { id?: string }).id) {
    redirect("/login");
  }
  const u = session.user as { id: string; email: string; name?: string; role: string };
  return { id: u.id, email: u.email, name: u.name, role: u.role as SessionUser["role"] };
}

/**
 * Resolve the active company for the current user.
 * Staff can have many memberships; the active company is stored in a cookie
 * set by /select-company. Clients have exactly one membership.
 */
export async function requireActiveCompany() {
  const user = await requireUser();
  const cookieStore = cookies();
  const cookieCompanyId = cookieStore.get(ACTIVE_COMPANY_COOKIE)?.value ?? null;

  const memberships = await prisma.membership.findMany({
    where: { userId: user.id },
    include: { company: true },
    orderBy: { createdAt: "asc" },
  });

  if (memberships.length === 0) {
    // Admins should go bootstrap companies; everyone else gets a friendly dead end.
    redirect(user.role === "ADMIN" ? "/admin" : "/no-access");
  }

  const active =
    (cookieCompanyId && memberships.find((m) => m.companyId === cookieCompanyId)) ||
    (memberships.length === 1 ? memberships[0] : null);

  if (!active) {
    redirect("/select-company");
  }

  return {
    user,
    membership: active,
    company: active.company,
    memberships,
  };
}

/** Pure helper used from API routes / server actions when we already know the user. */
export async function assertCompanyAccess(userId: string, companyId: string) {
  const m = await prisma.membership.findUnique({
    where: { userId_companyId: { userId, companyId } },
  });
  if (!m) throw new Error("Forbidden: no access to this company");
  return m;
}
