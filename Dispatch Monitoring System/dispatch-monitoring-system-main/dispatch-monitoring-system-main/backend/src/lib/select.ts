import { Prisma } from "@prisma/client";

export const csrPublicSelect = {
  id: true,
  name: true,
  email: true,
  role: true,
  last_login_at: true,
  created_at: true,
  updated_at: true,
} satisfies Prisma.CSRSelect;
