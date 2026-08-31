import type { Role } from "@prisma/client";

export interface AuthenticatedUser {
  id: number;
  name: string;
  email: string;
  role: Role;
  must_change_password: boolean;
}

declare global {
  namespace Express {
    interface Request {
      user?: AuthenticatedUser;
    }
  }

  interface BigInt {
    toJSON(): number;
  }
}

export {};
