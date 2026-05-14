import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    user: DefaultSession["user"] & {
      id: string;
      role: "PLATFORM_ADMIN" | "FIRM_ADMIN" | "STAFF" | "CLIENT" | "ADMIN";
      companyId: string | null;
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    uid?: string;
    role?: string;
    companyId?: string | null;
  }
}
