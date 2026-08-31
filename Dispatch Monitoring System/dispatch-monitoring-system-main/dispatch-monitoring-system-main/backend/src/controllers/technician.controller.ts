import { Request, Response } from "express";
import prisma from "../lib/prisma";
import { NotFoundError, ConflictError, ValidationError } from "../lib/errors";
import { parseIdParam } from "../lib/utils";
import { CreateTechnicianSchema, UpdateTechnicianSchema, DeleteTechnicianSchema } from "../lib/validators";
import { writeAudit } from "../lib/audit";
import { emitAuditChanged, emitEntityChanged } from "../lib/socket";

const activeTechnicianWhere = { deleted_at: null };

export async function listTechnicians(req: Request, res: Response) {
  const technicians = await prisma.technician.findMany({
    where: activeTechnicianWhere,
    orderBy: { name: "asc" },
    include: { team: true },
  });

  res.json({ success: true, data: technicians });
}

async function assertTeamExists(teamId: number | null | undefined): Promise<void> {
  if (teamId === null || teamId === undefined) return;
  const team = await prisma.team.findUnique({ where: { id: teamId } });
  if (!team) throw new NotFoundError("Team");
}

export async function createTechnician(req: Request, res: Response) {
  const body = CreateTechnicianSchema.parse(req.body);

  const existing = await prisma.technician.findUnique({
    where: { name: body.name },
  });

  if (existing) {
    throw new ConflictError("Technician with this name already exists");
  }

  await assertTeamExists(body.team_id);

  const technician = await prisma.technician.create({
    data: {
      name: body.name,
      contact_number: body.contact_number ?? null,
      target_per_day: body.target_per_day,
      target_per_month: body.target_per_month,
      team_id: body.team_id ?? null,
    },
    include: { team: true },
  });

  await writeAudit(prisma, {
    action: "CREATE",
    entity_type: "Technician",
    entity_id: technician.id,
    actor_id: req.user!.id,
    summary: `Created technician ${technician.name}`,
    after: {
      name: technician.name,
      contact_number: technician.contact_number,
      target_per_day: technician.target_per_day,
      target_per_month: technician.target_per_month,
      team: technician.team?.name ?? null,
    },
  });

  emitEntityChanged("technician:changed", technician.id);
  emitAuditChanged();

  res.status(201).json({ success: true, data: technician });
}

export async function updateTechnician(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = UpdateTechnicianSchema.parse(req.body);

  const existing = await prisma.technician.findFirst({
    where: { id, deleted_at: null },
    include: { team: true },
  });

  if (!existing) {
    throw new NotFoundError("Technician");
  }

  if (body.name) {
    const duplicate = await prisma.technician.findFirst({
      where: { name: body.name, NOT: { id } },
    });

    if (duplicate) {
      throw new ConflictError("Technician with this name already exists");
    }
  }

  if (body.team_id !== undefined) await assertTeamExists(body.team_id);

  const technician = await prisma.technician.update({
    where: { id, deleted_at: null },
    data: body,
    include: { team: true },
  });

  await writeAudit(prisma, {
    action: "UPDATE",
    entity_type: "Technician",
    entity_id: id,
    actor_id: req.user!.id,
    summary: `Updated technician ${technician.name}`,
    before: {
      name: existing.name,
      contact_number: existing.contact_number,
      target_per_day: existing.target_per_day,
      target_per_month: existing.target_per_month,
      team: existing.team?.name ?? null,
    },
    after: {
      name: technician.name,
      contact_number: technician.contact_number,
      target_per_day: technician.target_per_day,
      target_per_month: technician.target_per_month,
      team: technician.team?.name ?? null,
    },
  });

  emitEntityChanged("technician:changed", id);
  emitAuditChanged();

  res.json({ success: true, data: technician });
}

export async function deleteTechnician(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = DeleteTechnicianSchema.parse(req.body);

  const existing = await prisma.technician.findFirst({
    where: { id, ...activeTechnicianWhere },
  });

  if (!existing) {
    throw new NotFoundError("Technician");
  }

  if (body.confirm_name.trim() !== existing.name) {
    throw new ValidationError(
      "Confirmation name does not match. Type the technician name exactly to delete."
    );
  }

  const deleted = await prisma.technician.update({
    where: { id },
    data: { deleted_at: new Date() },
  });

  await writeAudit(prisma, {
    action: "DELETE",
    entity_type: "Technician",
    entity_id: id,
    actor_id: req.user!.id,
    summary: `Deleted technician ${existing.name}`,
    before: existing,
    after: deleted,
  });

  emitEntityChanged("technician:changed", id);
  emitAuditChanged();

  res.json({ success: true, data: { id } });
}