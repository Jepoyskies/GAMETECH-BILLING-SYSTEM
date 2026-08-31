import { Request, Response } from "express";
import prisma from "../lib/prisma";
import { NotFoundError, ConflictError, ValidationError, ForbiddenError } from "../lib/errors";
import { parseIdParam } from "../lib/utils";
import { writeAudit } from "../lib/audit";
import { CreateCSRSchema, UpdateCSRSchema, DeleteCSRSchema } from "../lib/validators";
import { emitAuditChanged, emitEntityChanged } from "../lib/socket";

const activeCSRWhere = { deleted_at: null };

export async function listCSR(req: Request, res: Response) {
  const csrs = await prisma.cSR.findMany({
    where: activeCSRWhere,
    select: {
      id: true,
      name: true,
      email: true,
      role: true,
      last_login_at: true,
      created_at: true,
      updated_at: true,
    },
    orderBy: { name: "asc" },
  });

  res.json({ success: true, data: csrs });
}

export async function createCSR(req: Request, res: Response) {
  const body = CreateCSRSchema.parse(req.body);

  const existing = await prisma.cSR.findFirst({
    where: { name: body.name, ...activeCSRWhere },
  });

  if (existing) {
    throw new ConflictError("CSR with this name already exists");
  }

  const csr = await prisma.$transaction(async (tx) => {
    const created = await tx.cSR.create({
      data: { name: body.name },
    });

    await writeAudit(tx, {
      action: "CREATE",
      entity_type: "CSR",
      entity_id: created.id,
      actor_id: req.user!.id,
      summary: `Created CSR ${created.name}`,
      after: { name: created.name },
    });

    emitEntityChanged("csr:changed", created.id);
    emitAuditChanged();
    return created;
  });

  res.status(201).json({ success: true, data: csr });
}

export async function updateCSR(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = UpdateCSRSchema.parse(req.body);

  const existing = await prisma.cSR.findFirst({
    where: { id, ...activeCSRWhere },
  });

  if (!existing) {
    throw new NotFoundError("CSR");
  }

  if (body.name) {
    const duplicate = await prisma.cSR.findFirst({
      where: { name: body.name, ...activeCSRWhere, NOT: { id } },
    });

    if (duplicate) {
      throw new ConflictError("CSR with this name already exists");
    }
  }

  const csr = await prisma.$transaction(async (tx) => {
    const updated = await tx.cSR.update({ where: { id, deleted_at: null }, data: body });
    await writeAudit(tx, {
      action: "UPDATE",
      entity_type: "CSR",
      entity_id: id,
      actor_id: req.user!.id,
      summary: `Updated CSR ${updated.name}`,
      before: existing,
      after: updated,
    });

    emitEntityChanged("csr:changed", id);
    emitAuditChanged();
    return updated;
  });

  res.json({ success: true, data: csr });
}

export async function deleteCSR(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = DeleteCSRSchema.parse(req.body);

  const existing = await prisma.cSR.findFirst({
    where: { id, ...activeCSRWhere },
  });

  if (!existing) {
    throw new NotFoundError("CSR");
  }

  if (existing.role === "SUPERADMIN") {
    throw new ForbiddenError("Cannot delete SUPERADMIN accounts");
  }

  if (body.confirm_name.trim() !== existing.name) {
    throw new ValidationError(
      "Confirmation name does not match. Type the CSR name exactly to delete."
    );
  }

  await prisma.$transaction(async (tx) => {
    const deleted = await tx.cSR.update({
      where: { id },
      data: { deleted_at: new Date() },
    });
    await writeAudit(tx, {
      action: "DELETE",
      entity_type: "CSR",
      entity_id: id,
      actor_id: req.user!.id,
      summary: `Deactivated CSR ${existing.name}`,
      before: existing,
      after: deleted,
    });

    emitEntityChanged("csr:changed", id);
    emitAuditChanged();
  });

  res.json({ success: true, data: { id } });
}