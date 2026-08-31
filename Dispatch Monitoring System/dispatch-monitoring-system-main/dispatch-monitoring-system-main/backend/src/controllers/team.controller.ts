import { Request, Response } from "express";
import prisma from "../lib/prisma";
import { NotFoundError, ConflictError } from "../lib/errors";
import { parseIdParam } from "../lib/utils";
import { writeAudit } from "../lib/audit";
import { CreateTeamSchema, UpdateTeamSchema } from "../lib/validators";
import { emitAuditChanged, emitEntityChanged } from "../lib/socket";

export async function listTeams(req: Request, res: Response) {
  const teams = await prisma.team.findMany({
    orderBy: { name: "asc" },
    include: { members: { orderBy: { name: "asc" } } },
  });

  res.json({ success: true, data: teams });
}

export async function createTeam(req: Request, res: Response) {
  const body = CreateTeamSchema.parse(req.body);

  const existing = await prisma.team.findUnique({ where: { name: body.name } });
  if (existing) throw new ConflictError("A team with this name already exists");

  const team = await prisma.team.create({
    data: { name: body.name },
    include: { members: true },
  });

  await writeAudit(prisma, {
    action: "CREATE",
    entity_type: "Team",
    entity_id: team.id,
    actor_id: req.user!.id,
    summary: `Created team ${team.name}`,
    after: { name: team.name },
  });

  emitEntityChanged("team:changed", team.id);
  emitAuditChanged();

  res.status(201).json({ success: true, data: team });
}

export async function updateTeam(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = UpdateTeamSchema.parse(req.body);

  const existing = await prisma.team.findUnique({ where: { id } });
  if (!existing) throw new NotFoundError("Team");

  if (body.name) {
    const duplicate = await prisma.team.findFirst({
      where: { name: body.name, NOT: { id } },
    });
    if (duplicate) throw new ConflictError("A team with this name already exists");
  }

  const team = await prisma.team.update({
    where: { id },
    data: body,
    include: { members: { orderBy: { name: "asc" } } },
  });

  await writeAudit(prisma, {
    action: "UPDATE",
    entity_type: "Team",
    entity_id: id,
    actor_id: req.user!.id,
    summary: `Updated team ${team.name}`,
    before: { name: existing.name },
    after: { name: team.name },
  });

  emitEntityChanged("team:changed", id);
  emitAuditChanged();

  res.json({ success: true, data: team });
}

export async function deleteTeam(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);

  const existing = await prisma.team.findUnique({ where: { id } });
  if (!existing) throw new NotFoundError("Team");

  await prisma.$transaction([
    prisma.technician.updateMany({ where: { team_id: id }, data: { team_id: null } }),
    prisma.team.delete({ where: { id } }),
  ]);

  await writeAudit(prisma, {
    action: "DELETE",
    entity_type: "Team",
    entity_id: id,
    actor_id: req.user!.id,
    summary: `Deleted team ${existing.name}`,
    before: { name: existing.name },
    after: { name: existing.name, deleted: true },
  });

  emitEntityChanged("team:changed", id);
  emitAuditChanged();

  res.json({ success: true, data: { id } });
}