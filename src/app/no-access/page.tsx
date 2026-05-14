import Link from "next/link";
import { resolveFirm } from "@/lib/firm";

export const dynamic = "force-dynamic";

export default async function NoAccessPage() {
  const firm = await resolveFirm();
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="card max-w-md text-center">
        <h1 className="text-lg font-semibold">No company access</h1>
        <p className="mt-2 text-sm text-slate-600">
          Your account isn&apos;t linked to any company yet. Please contact{" "}
          {firm.supportEmail ? (
            <a className="text-blue-600 underline" href={`mailto:${firm.supportEmail}`}>
              {firm.supportEmail}
            </a>
          ) : (
            "your administrator"
          )}{" "}
          to request access.
        </p>
        <Link href="/api/auth/signout" className="mt-4 inline-block text-sm text-blue-600 underline">
          Sign out
        </Link>
      </div>
    </main>
  );
}
