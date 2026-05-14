"use server";

import { cookies } from "next/headers";
import { requireUser, ACTIVE_COMPANY_COOKIE } from "@/lib/session";
import { prisma } from "@/lib/prisma";

export async function setActiveCompany(companyId: string) {
  const user = await requireUser();
  const m = await prisma.membership.findUnique({
    where: { userId_companyId: { userId: user.id, companyId } },
  });
  if (!m) throw new Error("Forbidden");
  cookies().set(ACTIVE_COMPANY_COOKIE, companyId, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
}

export async function clearActiveCompany() {
  cookies().delete(ACTIVE_COMPANY_COOKIE);
}
