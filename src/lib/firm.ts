import { cookies, headers } from "next/headers";
import { prisma } from "@/lib/prisma";

export const FIRM_OVERRIDE_COOKIE = "akr_firm_slug"; // dev-time override

export type ActiveFirm = {
  id: string;
  slug: string;
  name: string;
  productName: string;
  customDomain: string | null;
  isDefault: boolean;
  logoUrl: string | null;
  faviconUrl: string | null;
  primaryColor: string;
  accentColor: string;
  supportEmail: string | null;
  footerText: string | null;
};

/**
 * Pick the active firm for the current request.
 *
 * Production: Host header → `Firm.customDomain` match.
 * Dev / no match: fall back to the platform's default firm.
 * Manual override: `?firm=<slug>` query param (one-shot) or `akr_firm_slug` cookie.
 */
export async function resolveFirm(): Promise<ActiveFirm> {
  const h = headers();
  const host = (h.get("x-forwarded-host") || h.get("host") || "").toLowerCase().split(":")[0];

  // Dev override via cookie
  const cookieSlug = cookies().get(FIRM_OVERRIDE_COOKIE)?.value;

  let firm = null as Awaited<ReturnType<typeof prisma.firm.findFirst>>;

  if (host) {
    firm = await prisma.firm.findFirst({
      where: { customDomain: host, isActive: true },
    });
  }
  if (!firm && cookieSlug) {
    firm = await prisma.firm.findFirst({
      where: { slug: cookieSlug, isActive: true },
    });
  }
  if (!firm) {
    firm = await prisma.firm.findFirst({
      where: { isDefault: true, isActive: true },
    });
  }
  if (!firm) {
    // Last-resort safety net so the app never crashes if seed missed.
    firm = await prisma.firm.create({
      data: { slug: "platform", name: "Platform", productName: "MCA Workspace", isDefault: true },
    });
  }

  return {
    id: firm.id,
    slug: firm.slug,
    name: firm.name,
    productName: firm.productName,
    customDomain: firm.customDomain,
    isDefault: firm.isDefault,
    logoUrl: firm.logoUrl,
    faviconUrl: firm.faviconUrl,
    primaryColor: firm.primaryColor,
    accentColor: firm.accentColor,
    supportEmail: firm.supportEmail,
    footerText: firm.footerText,
  };
}

/** Convert the firm's branding into inline CSS variables for the root element. */
export function brandingStyle(firm: ActiveFirm): React.CSSProperties {
  const primary = hexToRgbChannels(firm.primaryColor) || "31 41 55";
  const accent = hexToRgbChannels(firm.accentColor) || "37 99 235";
  return {
    ["--brand-primary" as never]: firm.primaryColor,
    ["--brand-accent" as never]: firm.accentColor,
    ["--brand-primary-rgb" as never]: primary,
    ["--brand-accent-rgb" as never]: accent,
  };
}

function hexToRgbChannels(hex: string): string | null {
  if (!hex) return null;
  const s = hex.replace("#", "").trim();
  const expanded = s.length === 3 ? s.split("").map((c) => c + c).join("") : s;
  if (!/^[0-9a-f]{6}$/i.test(expanded)) return null;
  const r = parseInt(expanded.slice(0, 2), 16);
  const g = parseInt(expanded.slice(2, 4), 16);
  const b = parseInt(expanded.slice(4, 6), 16);
  return `${r} ${g} ${b}`;
}
