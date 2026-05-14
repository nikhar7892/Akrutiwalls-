import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  // 1. Default Firm — the platform's own / fallback tenant.
  const firm = await prisma.firm.upsert({
    where: { slug: "platform" },
    create: {
      slug: "platform",
      name: "Platform",
      productName: "MCA Workspace",
      isDefault: true,
      isActive: true,
      primaryColor: "#1f2937",
      accentColor: "#2563eb",
      supportEmail: process.env.SEED_ADMIN_EMAIL || "admin@akrutiwalls.local",
      footerText: "Confidential — for authorised users only.",
    },
    update: {},
  });

  // 2. Admin user, attached to the platform firm.
  const adminEmail = (process.env.SEED_ADMIN_EMAIL || "admin@akrutiwalls.local").toLowerCase();
  const adminPassword = process.env.SEED_ADMIN_PASSWORD || "changeme123";
  const passwordHash = await bcrypt.hash(adminPassword, 10);

  const admin = await prisma.user.upsert({
    where: { email: adminEmail },
    create: {
      email: adminEmail,
      passwordHash,
      name: "Platform Admin",
      role: "PLATFORM_ADMIN",
      firmId: firm.id,
    },
    update: { firmId: firm.id },
  });

  // 3. Backfill any pre-existing users / companies without a firm to the platform firm.
  await prisma.user.updateMany({
    where: { firmId: null },
    data: { firmId: firm.id },
  });
  await prisma.company.updateMany({
    where: { firmId: null },
    data: { firmId: firm.id },
  });

  // 4. Migrate legacy "ADMIN" role to PLATFORM_ADMIN.
  await prisma.user.updateMany({
    where: { role: "ADMIN" },
    data: { role: "PLATFORM_ADMIN" },
  });

  console.log(`Default firm ready: ${firm.slug} (${firm.id})`);
  console.log(`Admin user ready: ${admin.email}`);
  console.log(`Password: ${adminPassword}`);
  console.log("Sign in, then go to /admin to create firms and link companies.");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
