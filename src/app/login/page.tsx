import { resolveFirm } from "@/lib/firm";
import { LoginForm } from "./login-form";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const firm = await resolveFirm();
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md card">
        <div className="flex items-center gap-3">
          {firm.logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={firm.logoUrl} alt="" className="h-10 w-10 rounded object-contain" />
          ) : null}
          <div>
            <h1 className="text-xl font-semibold text-slate-900">{firm.productName}</h1>
            <p className="mt-1 text-sm text-slate-500">Sign in to your workspace.</p>
          </div>
        </div>
        <LoginForm />
        {firm.footerText && (
          <p className="mt-6 text-center text-xs text-slate-400">{firm.footerText}</p>
        )}
      </div>
    </main>
  );
}
