import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

const BCRYPT_ROUNDS = 12;

interface AdminSeed {
  email: string;
  name: string;
  password: string;
  role?: "SUPERADMIN" | "CSR_ADMIN";
}

const ACCOUNTS: AdminSeed[] = [
  { email: "superadmin@gametech.com", name: "Gametech Admin", password: "eeeeeeee", role: "SUPERADMIN" },
  // Add more accounts below:
  // { email: "glennmarkanino@gmail.com", name: "Glenn Anino", password: "20052013", role: "SUPERADMIN" },
];

async function seedAccount(account: AdminSeed) {
  const existing = await prisma.cSR.findFirst({
    where: { email: { equals: account.email, mode: "insensitive" } },
  });

  if (existing) {
    console.log(`  Skipped — ${account.email} already exists`);
    return;
  }

  const passwordHash = await bcrypt.hash(account.password, BCRYPT_ROUNDS);

  await prisma.cSR.create({
    data: {
      email: account.email,
      name: account.name,
      password_hash: passwordHash,
      role: account.role ?? "SUPERADMIN",
    },
  });

  console.log(`  ✓ ${account.email} (${account.name})`);
}

async function main() {
  console.log("Seeding admin accounts...");
  for (const account of ACCOUNTS) {
    await seedAccount(account);
  }
  console.log("Done.");
}

main()
  .catch((e) => {
    console.error("Seed failed:", e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());