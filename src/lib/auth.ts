import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";
import { prisma } from "@/lib/prisma";

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt", maxAge: 60 * 60 * 8 }, // 8h
  pages: { signIn: "/login" },
  providers: [
    CredentialsProvider({
      name: "Email + password",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials.password) return null;
        const user = await prisma.user.findUnique({
          where: { email: credentials.email.toLowerCase().trim() },
        });
        if (!user || !user.isActive) return null;
        const ok = await bcrypt.compare(credentials.password, user.passwordHash);
        if (!ok) return null;
        return { id: user.id, email: user.email, name: user.name ?? user.email, role: user.role };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, trigger, session }) {
      if (user) {
        token.uid = (user as { id: string }).id;
        token.role = (user as { role: string }).role;
        token.companyId = null;
      }
      // Allow the client to switch the active company via `update({ companyId })`
      if (trigger === "update" && session && "companyId" in session) {
        token.companyId = (session as { companyId: string | null }).companyId;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as { id?: string }).id = token.uid as string;
        (session.user as { role?: string }).role = token.role as string;
        (session.user as { companyId?: string | null }).companyId =
          (token.companyId as string | null) ?? null;
      }
      return session;
    },
  },
};
