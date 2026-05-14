import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const adminEmail = (process.env.SEED_ADMIN_EMAIL || "admin@akrutiwalls.local").toLowerCase();
  const adminPassword = process.env.SEED_ADMIN_PASSWORD || "changeme123";
  const passwordHash = await bcrypt.hash(adminPassword, 10);

  const admin = await prisma.user.upsert({
    where: { email: adminEmail },
    create: {
      email: adminEmail,
      passwordHash,
      name: "Akrutiwalls Admin",
      role: "ADMIN",
    },
    update: {},
  });

  console.log(`Admin user ready: ${admin.email}`);
  console.log("Sign in, then visit /admin to create companies, users and grant memberships.");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
