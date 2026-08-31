import { Request, Response, NextFunction } from "express";
import prisma from "../lib/prisma";
import { AUTH_COOKIE, verifyToken } from "../lib/auth";
import { AppError } from "../lib/errors";

class UnauthorizedError extends AppError {
  constructor(message = "Authentication required") {
    super(message, 401);
  }
}

class ForbiddenError extends AppError {
  constructor(message = "You do not have permission to perform this action") {
    super(message, 403);
  }
}

export async function requireAuth(
  req: Request,
  _res: Response,
  next: NextFunction
): Promise<void> {
  const token = req.cookies?.[AUTH_COOKIE];
  if (!token) throw new UnauthorizedError();

  let payload;
  try {
    payload = verifyToken(token);
  } catch {
    throw new UnauthorizedError("Session expired or invalid. Please log in again.");
  }

  const csr = await prisma.cSR.findFirst({
    where: { id: payload.sub, deleted_at: null },
  });

  if (!csr || !csr.role || !csr.email || !csr.password_hash) {
    throw new UnauthorizedError("Account no longer active. Please log in again.");
  }

  req.user = {
    id: csr.id,
    name: csr.name,
    email: csr.email,
    role: csr.role,
    must_change_password: csr.must_change_password,
  };
  next();
}

export function requireSuperAdmin(
  req: Request,
  _res: Response,
  next: NextFunction
): void {
  if (!req.user) throw new UnauthorizedError();
  if (req.user.role !== "SUPERADMIN") {
    throw new ForbiddenError("Only the SUPERADMIN can perform this action.");
  }
  next();
}
