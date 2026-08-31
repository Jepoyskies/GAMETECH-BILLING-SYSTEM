import { Request, Response } from "express";
import { CSR } from "@prisma/client";
import prisma from "../lib/prisma";
import {
  AUTH_COOKIE,
  LOCKOUT_MINUTES,
  MAX_FAILED_ATTEMPTS,
  authCookieOptions,
  hashPassword,
  signToken,
  verifyPassword,
} from "../lib/auth";
import {
  AppError,
  ConflictError,
  ForbiddenError,
  ValidationError,
} from "../lib/errors";
import { writeAudit } from "../lib/audit";
import { emitAuditChanged, emitEntityChanged } from "../lib/socket";
import {
  CreateAccountSchema,
  LoginSchema,
  SetupSchema,
  UpdateAccountSchema,
  UpdatePasswordSchema,
} from "../lib/validators";
import { parseIdParam } from "../lib/utils";

class UnauthorizedError extends AppError {
  constructor(message: string) {
    super(message, 401);
  }
}

function toPublicAccount(csr: CSR) {
  return {
    id: csr.id,
    name: csr.name,
    email: csr.email,
    role: csr.role,
    last_login_at: csr.last_login_at,
    must_change_password: csr.must_change_password,
    created_at: csr.created_at,
    updated_at: csr.updated_at,
  };
}

const accountWhere = {
  deleted_at: null,
  role: { not: null },
  email: { not: null },
};

async function accountExists(): Promise<boolean> {
  const count = await prisma.cSR.count({ where: accountWhere });
  return count > 0;
}

function issueSession(res: Response, csr: CSR) {
  const token = signToken({
    sub: csr.id,
    role: csr.role!,
    email: csr.email!,
  });
  res.cookie(AUTH_COOKIE, token, authCookieOptions());
}

// GET /api/auth/setup
export async function getSetupStatus(_req: Request, res: Response) {
  res.json({ success: true, data: { needs_setup: !(await accountExists()) } });
}

// POST /api/auth/setup
export async function setup(req: Request, res: Response) {
  const body = SetupSchema.parse(req.body);

  if (await accountExists()) {
    throw new ForbiddenError(
      "Setup has already been completed. Ask the SUPERADMIN to create your account."
    );
  }

  const password_hash = await hashPassword(body.password);

  const csr = await prisma.$transaction(async (tx) => {
    const created = await tx.cSR.create({
      data: {
        name: body.name,
        email: body.email,
        password_hash,
        role: "SUPERADMIN",
      },
    });
    await writeAudit(tx, {
      action: "CREATE",
      entity_type: "CSR",
      entity_id: created.id,
      actor_id: created.id,
      summary: `Initial SUPERADMIN account created (${created.email})`,
      after: { name: created.name, email: created.email, role: created.role },
    });

    emitEntityChanged("csr:changed", created.id);
    emitAuditChanged();
    return created;
  });

  issueSession(res, csr);
  res.status(201).json({ success: true, data: toPublicAccount(csr) });
}

// POST /api/auth/login — email + password, with per-account lockout.
export async function login(req: Request, res: Response) {
  const { email, password } = LoginSchema.parse(req.body);

  const csr = await prisma.cSR.findFirst({
    where: { email, deleted_at: null },
  });

  const invalid = new UnauthorizedError("Invalid email or password");

  if (!csr || !csr.password_hash || !csr.role) {
    throw invalid;
  }

  if (csr.locked_until && csr.locked_until.getTime() > Date.now()) {
    const mins = Math.ceil((csr.locked_until.getTime() - Date.now()) / 60000);
    throw new UnauthorizedError(
      `Account temporarily locked due to failed login attempts. Try again in ${mins} minute(s).`
    );
  }

  const ok = await verifyPassword(password, csr.password_hash);

  if (!ok) {
    const attempts = csr.failed_login_attempts + 1;
    const lock = attempts >= MAX_FAILED_ATTEMPTS;
    await prisma.cSR.update({
      where: { id: csr.id },
      data: {
        failed_login_attempts: lock ? 0 : attempts,
        locked_until: lock
          ? new Date(Date.now() + LOCKOUT_MINUTES * 60000)
          : csr.locked_until,
      },
    });
    if (lock) {
      throw new UnauthorizedError(
        `Too many failed attempts. Account locked for ${LOCKOUT_MINUTES} minutes.`
      );
    }
    throw invalid;
  }

  const updated = await prisma.cSR.update({
    where: { id: csr.id },
    data: {
      failed_login_attempts: 0,
      locked_until: null,
      last_login_at: new Date(),
    },
  });

  issueSession(res, updated);
  res.json({ success: true, data: toPublicAccount(updated) });
}

// POST /api/auth/logout
export async function logout(_req: Request, res: Response) {
  res.clearCookie(AUTH_COOKIE, authCookieOptions());
  res.json({ success: true });
}

// GET /api/auth/me
export async function me(req: Request, res: Response) {
  res.json({ success: true, data: req.user });
}

// POST /api/auth/accounts — SUPERADMIN only. Creates a CSR_ADMIN account.
export async function createAccount(req: Request, res: Response) {
  const actor = req.user!;
  const body = CreateAccountSchema.parse(req.body);

  // Re-verify the SUPERADMIN's own credentials ("with valid credentials").
  const superadmin = await prisma.cSR.findFirst({
    where: { id: actor.id, deleted_at: null },
  });
  if (!superadmin?.password_hash) {
    throw new UnauthorizedError("Your session is no longer valid. Please log in again.");
  }
  const credentialsOk = await verifyPassword(body.current_password, superadmin.password_hash);
  if (!credentialsOk) {
    throw new ValidationError("Your current password is incorrect.");
  }

  const existing = await prisma.cSR.findFirst({
    where: { email: body.email, deleted_at: null },
  });
  if (existing) {
    throw new ConflictError("An account with this email already exists.");
  }

  const password_hash = await hashPassword(body.password);

  const created = await prisma.$transaction(async (tx) => {
    const account = await tx.cSR.create({
      data: {
        name: body.name,
        email: body.email,
        password_hash,
        role: "CSR_ADMIN",
        must_change_password: true,
      },
    });
    await writeAudit(tx, {
      action: "CREATE",
      entity_type: "CSR",
      entity_id: account.id,
      actor_id: actor.id,
      summary: `Created CSR_ADMIN account ${account.name} (${account.email})`,
      after: { name: account.name, email: account.email, role: account.role, must_change_password: account.must_change_password },
    });

    emitEntityChanged("csr:changed", account.id);
    emitAuditChanged();
    return account;
  });

  res.status(201).json({ success: true, data: toPublicAccount(created) });
}

// GET /api/auth/accounts — list all CSR accounts (authenticated users).
export async function listAccounts(_req: Request, res: Response) {
  const accounts = await prisma.cSR.findMany({
    where: accountWhere,
    orderBy: [{ role: "asc" }, { name: "asc" }],
  });
  res.json({ success: true, data: accounts.map(toPublicAccount) });
}

// PUT /api/auth/accounts/:id — Edits an account's name/email.
export async function updateAccount(req: Request, res: Response) {
  const actor = req.user!;
  const id = parseIdParam(req.params.id);
  const body = UpdateAccountSchema.parse(req.body);

  if (Object.keys(body).length === 0) {
    throw new ValidationError("Provide at least one field to update");
  }

  if (actor.role !== "SUPERADMIN" && actor.id !== id) {
    throw new ForbiddenError("You can only edit your own account.");
  }

  const existing = await prisma.cSR.findFirst({
    where: { id, ...accountWhere },
  });
  if (!existing) {
    throw new ConflictError("Account not found.");
  }

  if (body.email && body.email !== existing.email) {
    const duplicate = await prisma.cSR.findFirst({
      where: { email: body.email, deleted_at: null, NOT: { id } },
    });
    if (duplicate) {
      throw new ConflictError("An account with this email already exists.");
    }
  }

  const updated = await prisma.$transaction(async (tx) => {
    const result = await tx.cSR.update({
      where: { id },
      data: body,
    });
    await writeAudit(tx, {
      action: "UPDATE",
      entity_type: "CSR",
      entity_id: id,
      actor_id: actor.id,
      summary: `Updated account ${result.name}`,
      before: { name: existing.name, email: existing.email },
      after: { name: result.name, email: result.email },
    });

    emitEntityChanged("csr:changed", id);
    emitAuditChanged();
    return result;
  });

  res.json({ success: true, data: toPublicAccount(updated) });
}

// PUT /api/auth/accounts/:id/password
export async function updateAccountPassword(req: Request, res: Response) {
  const actor = req.user!;
  const id = parseIdParam(req.params.id);
  const body = UpdatePasswordSchema.parse(req.body);

  const target = await prisma.cSR.findFirst({
    where: { id, deleted_at: null },
  });
  if (!target) {
    throw new ConflictError("Account not found.");
  }

  if (actor.id === id) {
    if (body.current_password) {
      const actorRecord = await prisma.cSR.findFirst({
        where: { id: actor.id, deleted_at: null },
      });
      if (!actorRecord?.password_hash) {
        throw new UnauthorizedError("Your session is no longer valid. Please log in again.");
      }
      const ok = await verifyPassword(body.current_password, actorRecord.password_hash);
      if (!ok) {
        throw new ValidationError("Current password is incorrect.");
      }
    } else if (!target.must_change_password) {
      throw new ValidationError("Current password is required to change your own password.");
    }
  } else {
    if (actor.role !== "SUPERADMIN") {
      throw new ForbiddenError("Only the SUPERADMIN can change another user's password.");
    }
  }

  const password_hash = await hashPassword(body.new_password);

  const updated = await prisma.$transaction(async (tx) => {
    const result = await tx.cSR.update({
      where: { id },
      data: { password_hash, must_change_password: actor.id !== id },
    });
    const wasSelfService = actor.id === id;
    await writeAudit(tx, {
      action: "UPDATE",
      entity_type: "CSR",
      entity_id: id,
      actor_id: actor.id,
      summary: wasSelfService
        ? `${actor.name} changed own password`
        : `${actor.name} (SUPERADMIN) reset password for ${target.name}`,
      before: { must_change_password: target.must_change_password },
      after: { must_change_password: result.must_change_password },
    });

    emitEntityChanged("csr:changed", id);
    emitAuditChanged();
    return result;
  });

  if (actor.id === id && !target.must_change_password) {
    res.clearCookie(AUTH_COOKIE, authCookieOptions());
  }

  res.json({ success: true, data: toPublicAccount(updated) });
}