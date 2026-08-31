import { Request, Response } from "express";
import { Prisma } from "@prisma/client";
import prisma from "../lib/prisma";
import { AuditQuerySchema } from "../lib/validators";
import { buildDateRangeFilter } from "../lib/queryFilters";

// GET /api/audit
export async function listAuditLogs(req: Request, res: Response) {
  const query = AuditQuerySchema.parse(req.query);
  const { action, entity_type, entity_id, actor, summary, date_from, date_to, cursor, limit } = query;

  const dateRange = buildDateRangeFilter(date_from, date_to);

  const where: Prisma.AuditLogWhereInput = {
    ...(action && { action }),
    ...(entity_type && { entity_type }),
    ...(entity_id && { entity_id }),
    ...(actor && { actor_id: actor }),
    ...(summary && { summary: { contains: summary, mode: "insensitive" } }),
    ...(dateRange.date && { created_at: dateRange.date }),
  };

  const logs = await prisma.auditLog.findMany({
    where,
    include: { actor: { select: { id: true, name: true, email: true, role: true } } },
    orderBy: [{ created_at: "desc" }, { id: "desc" }],
    ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
    take: limit + 1,
  });

  const hasNext = logs.length > limit;
  const data = hasNext ? logs.slice(0, limit) : logs;
  const nextCursor = hasNext ? data[data.length - 1].id : null;

  res.json({
    success: true,
    data,
    pagination: { next_cursor: nextCursor, has_next: hasNext, limit },
  });
}