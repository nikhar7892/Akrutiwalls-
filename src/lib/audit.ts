import { prisma } from "@/lib/prisma";

type AuditInput = {
  companyId?: string | null;
  userId?: string | null;
  entity: string;
  entityId?: string | null;
  action: "create" | "update" | "delete";
  before?: unknown;
  after?: unknown;
};

/** Convert BigInt / Decimal / Date into JSON-safe primitives before persistence. */
function safe(value: unknown): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === "bigint") return value.toString();
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "object") {
    // Prisma Decimal has a toJSON / toString
    const maybe = value as { toJSON?: () => unknown };
    if (typeof maybe.toJSON === "function" && !(value instanceof Array)) {
      const v = maybe.toJSON();
      if (typeof v !== "object" || v === null) return v;
    }
    if (Array.isArray(value)) return value.map(safe);
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) out[k] = safe(v);
    return out;
  }
  return value;
}

export async function recordAudit(input: AuditInput) {
  try {
    await prisma.auditLog.create({
      data: {
        companyId: input.companyId ?? null,
        userId: input.userId ?? null,
        entity: input.entity,
        entityId: input.entityId ?? null,
        action: input.action,
        before: (safe(input.before) ?? undefined) as never,
        after: (safe(input.after) ?? undefined) as never,
      },
    });
  } catch (err) {
    // Auditing must never break the user action; surface to logs.
    console.error("recordAudit failed", err);
  }
}
