import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { brandingStyle, resolveFirm } from "@/lib/firm";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const firm = await resolveFirm();
  return {
    title: firm.productName,
    description: "Company master, compliance documents and filings.",
    icons: firm.faviconUrl ? { icon: firm.faviconUrl } : undefined,
  };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const firm = await resolveFirm();
  return (
    <html lang="en" style={brandingStyle(firm)}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
