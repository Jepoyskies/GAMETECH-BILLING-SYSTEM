import { Request, Response } from "express";
import { Prisma } from "@prisma/client";
import prisma from "../lib/prisma";
import { NotFoundError, ValidationError } from "../lib/errors";
import { parseIdParam } from "../lib/utils";
import { writeAudit } from "../lib/audit";
import { emitAuditChanged, emitEntityChanged } from "../lib/socket";
import {
  CreateCustomerSchema,
  UpdateCustomerSchema,
  DeleteCustomerSchema,
  CustomerQuerySchema,
  CustomerSearchQuerySchema,
} from "../lib/validators";

const activeWhere = { deleted_at: null };

export async function listCustomers(req: Request, res: Response) {
  const { search, sort, page, limit } = CustomerQuerySchema.parse(req.query);
  const skip = (page - 1) * limit;

  const where: Prisma.CustomerWhereInput = {
    ...activeWhere,
    ...(search && {
      OR: [
        { name: { contains: search, mode: "insensitive" } },
        { contact_number: { contains: search, mode: "insensitive" } },
        { account_number: { contains: search, mode: "insensitive" } },
        { barangay_city: { contains: search, mode: "insensitive" } },
      ],
    }),
  };

  const orderBy =
    sort === "created_desc"
      ? ({ created_at: "desc" } as const)
      : ({ name: "asc" } as const);

  const [customers, total] = await Promise.all([
    prisma.customer.findMany({
      where,
      orderBy,
      skip,
      take: limit,
    }),
    prisma.customer.count({ where }),
  ]);

  res.json({
    success: true,
    data: customers,
    pagination: { total, page, limit, total_pages: Math.ceil(total / limit) },
  });
}

export async function checkAccountNumber(req: Request, res: Response) {
  const accountNumber = req.query.account_number as string | undefined;
  const excludeId = req.query.exclude_id ? Number(req.query.exclude_id) : undefined;

  if (!accountNumber) {
    res.json({ success: true, data: { exists: false } });
    return;
  }

  const where: Prisma.CustomerWhereInput = {
    account_number: accountNumber,
  };

  if (excludeId && !isNaN(excludeId)) {
    where.id = { not: excludeId };
  }

  const existing = await prisma.customer.findFirst({ where, select: { id: true } });

  res.json({ success: true, data: { exists: !!existing } });
}

export async function checkName(req: Request, res: Response) {
  const name = req.query.name as string | undefined;
  const excludeId = req.query.exclude_id ? Number(req.query.exclude_id) : undefined;

  if (!name || !name.trim()) {
    res.json({ success: true, data: { exists: false } });
    return;
  }

  const where: Prisma.CustomerWhereInput = {
    name: { equals: name.trim(), mode: "insensitive" },
    deleted_at: null,
  };

  if (excludeId && !isNaN(excludeId)) {
    where.id = { not: excludeId };
  }

  const existing = await prisma.customer.findFirst({ where, select: { id: true } });

  res.json({ success: true, data: { exists: !!existing } });
}

export async function searchCustomers(req: Request, res: Response) {
  const { q, limit } = CustomerSearchQuerySchema.parse(req.query);

  if (!q) {
    res.json({ success: true, data: [] });
    return;
  }

  const customers = await prisma.customer.findMany({
    where: {
      ...activeWhere,
      OR: [
        { name: { contains: q, mode: "insensitive" } },
        { contact_number: { contains: q, mode: "insensitive" } },
        { account_number: { contains: q, mode: "insensitive" } },
      ],
    },
    select: { id: true, name: true, address: true, contact_number: true, account_number: true, email: true, barangay_city: true, latitude: true, longitude: true },
    orderBy: { name: "asc" },
    take: limit,
  });

  res.json({ success: true, data: customers });
}

export async function getCustomer(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const customer = await prisma.customer.findFirst({ where: { id, ...activeWhere } });
  if (!customer) throw new NotFoundError("Customer");
  res.json({ success: true, data: customer });
}

const UNASSIGNED_TYPE = "UNASSIGNED";

export async function getCustomerStats(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);

  const customer = await prisma.customer.findFirst({ where: { id, ...activeWhere } });
  if (!customer) throw new NotFoundError("Customer");

  const baseWhere = { customer_id: id, deleted_at: null };

  const monitoringWhere = { ...baseWhere, dispatch: null };

  const [dispatchStatus, dispatchType, monitoringStatus, monitoringType] = await Promise.all([
    prisma.dispatch.groupBy({ by: ["status_id"], where: baseWhere, _count: { _all: true } }),
    prisma.dispatch.groupBy({ by: ["type_id"], where: baseWhere, _count: { _all: true } }),
    prisma.monitoringRecord.groupBy({ by: ["status_id"], where: monitoringWhere, _count: { _all: true } }),
    prisma.monitoringRecord.groupBy({ by: ["type_id"], where: monitoringWhere, _count: { _all: true } }),
  ]);

  const allIds = new Set<number>();
  dispatchStatus.forEach((r) => allIds.add(r.status_id));
  monitoringStatus.forEach((r) => allIds.add(r.status_id));
  dispatchType.forEach((r) => r.type_id && allIds.add(r.type_id));
  monitoringType.forEach((r) => r.type_id && allIds.add(r.type_id));

  const optionRows = await prisma.configOption.findMany({ where: { id: { in: [...allIds] } } });
  const labelById = new Map(optionRows.map((o) => [o.id, o.label]));

  const byStatus: Record<string, number> = {};
  for (const row of dispatchStatus) {
    const label = labelById.get(row.status_id) ?? "Unknown";
    byStatus[label] = (byStatus[label] ?? 0) + row._count._all;
  }
  for (const row of monitoringStatus) {
    const label = labelById.get(row.status_id) ?? "Unknown";
    byStatus[label] = (byStatus[label] ?? 0) + row._count._all;
  }

  const byType: Record<string, number> = {};
  for (const row of dispatchType) {
    const label = row.type_id ? labelById.get(row.type_id) ?? "Unknown" : UNASSIGNED_TYPE;
    byType[label] = (byType[label] ?? 0) + row._count._all;
  }
  for (const row of monitoringType) {
    const label = row.type_id ? labelById.get(row.type_id) ?? "Unknown" : UNASSIGNED_TYPE;
    byType[label] = (byType[label] ?? 0) + row._count._all;
  }

  const dispatchTotal = dispatchStatus.reduce((sum, r) => sum + r._count._all, 0);
  const monitoringTotal = monitoringStatus.reduce((sum, r) => sum + r._count._all, 0);

  res.json({
    success: true,
    data: {
      total_jobs: dispatchTotal + monitoringTotal,
      dispatch_total: dispatchTotal,
      monitoring_total: monitoringTotal,
      by_status: byStatus,
      by_type: byType,
    },
  });
}

export async function getCustomerJobs(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const { page, limit } = CustomerQuerySchema.parse(req.query);

  const customer = await prisma.customer.findFirst({ where: { id, ...activeWhere } });
  if (!customer) throw new NotFoundError("Customer");

  const offset = (page - 1) * limit;

  const [countResult, rows] = await Promise.all([
    prisma.$queryRawUnsafe<Array<{ total: bigint }>>(
      `SELECT COUNT(*)::bigint AS total FROM (
        SELECT id FROM "Dispatch" WHERE customer_id = $1 AND deleted_at IS NULL
        UNION ALL
        SELECT id FROM "MonitoringRecord" WHERE customer_id = $1 AND deleted_at IS NULL AND NOT EXISTS (SELECT 1 FROM "Dispatch" WHERE monitoring_id = "MonitoringRecord".id)
      ) AS jobs`,
      id
    ),
    prisma.$queryRawUnsafe<
      Array<{
        id: number;
        date: Date;
        client: string;
        address: string;
        contact_number: string;
        concern: string;
        ticket_number: string | null;
        latitude: number | null;
        longitude: number | null;
        time_start: Date | null;
        done_at: Date | null;
        source: string;
        module: string;
        type_label: string | null;
        status_label: string;
      }>
    >(
      `SELECT
        d.id, d.date, d.client, d.address, d.contact_number, d.concern,
        d.ticket_number, d.latitude, d.longitude,
        d.time_start, d.done_at,
        'DISPATCH' AS source, 'DISPATCH_LOG' AS module,
        dt.label AS type_label, ds.label AS status_label
      FROM "Dispatch" d
      LEFT JOIN "ConfigOption" dt ON d.type_id = dt.id
      LEFT JOIN "ConfigOption" ds ON d.status_id = ds.id
      WHERE d.customer_id = $1 AND d.deleted_at IS NULL

      UNION ALL

      SELECT
        m.id, m.date, m.client, m.address, m.contact_number, m.concern,
        m.ticket_number, m.latitude, m.longitude,
        m.time_start, m.done_at,
        'MONITORING' AS source, m.tab_type::text AS module,
        mt.label AS type_label, ms.label AS status_label
      FROM "MonitoringRecord" m
      LEFT JOIN "ConfigOption" mt ON m.type_id = mt.id
      LEFT JOIN "ConfigOption" ms ON m.status_id = ms.id
      WHERE m.customer_id = $1 AND m.deleted_at IS NULL AND NOT EXISTS (SELECT 1 FROM "Dispatch" WHERE monitoring_id = m.id)

      ORDER BY date DESC
      LIMIT $2 OFFSET $3`,
      id, limit, offset
    ),
  ]);

  const total = Number(countResult[0]?.total ?? 0);
  const data = rows.map((r) => ({
    source: r.source,
    module: r.module,
    id: r.id,
    date: r.date,
    client: r.client,
    address: r.address,
    contact_number: r.contact_number,
    concern: r.concern,
    type: r.type_label,
    status: r.status_label,
    ticket_number: r.ticket_number,
    latitude: r.latitude,
    longitude: r.longitude,
    time_start: r.time_start,
    done_at: r.done_at,
  }));

  res.json({
    success: true,
    data,
    pagination: { total, page, limit, total_pages: Math.ceil(total / limit) },
  });
}

export async function createCustomer(req: Request, res: Response) {
  const body = CreateCustomerSchema.parse(req.body);

  const customer = await prisma.$transaction(async (tx) => {
    const created = await tx.customer.create({ data: body });
    await writeAudit(tx, {
      action: "CREATE",
      entity_type: "Customer",
      entity_id: created.id,
      actor_id: req.user!.id,
      summary: `Created customer ${created.name}`,
      after: created,
    });

    emitEntityChanged("customer:changed", created.id);
    emitAuditChanged();
    return created;
  });

  res.status(201).json({ success: true, data: customer });
}

export async function updateCustomer(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = UpdateCustomerSchema.parse(req.body);

  const customer = await prisma.$transaction(async (tx) => {
    const existing = await tx.customer.findFirst({ where: { id, ...activeWhere } });
    if (!existing) throw new NotFoundError("Customer");

    const updated = await tx.customer.update({ where: { id, deleted_at: null }, data: body });

    await Promise.all([
      tx.dispatch.updateMany({
        where: { customer_id: id, deleted_at: null },
        data: {
          client: updated.name,
          address: updated.address,
          contact_number: updated.contact_number,
          latitude: updated.latitude,
          longitude: updated.longitude,
        },
      }),
      tx.monitoringRecord.updateMany({
        where: { customer_id: id, deleted_at: null },
        data: {
          client: updated.name,
          address: updated.address,
          contact_number: updated.contact_number,
          latitude: updated.latitude,
          longitude: updated.longitude,
        },
      }),
    ]);

    const monitoringIds = (
      await tx.monitoringRecord.findMany({
        where: { customer_id: id, deleted_at: null },
        select: { id: true },
      })
    ).map((r) => r.id);

    if (monitoringIds.length > 0) {
      await tx.jobDetail.updateMany({
        where: { record_id: { in: monitoringIds } },
        data: {
          email_address: updated.email,
          barangay_city: updated.barangay_city,
          account_no: updated.account_number,
        },
      });
    }

    await writeAudit(tx, {
      action: "UPDATE",
      entity_type: "Customer",
      entity_id: id,
      actor_id: req.user!.id,
      summary: `Updated customer ${updated.name}`,
      before: existing,
      after: updated,
    });

    emitEntityChanged("customer:changed", id);
    emitAuditChanged();
    return updated;
  });

  res.json({ success: true, data: customer });
}

export async function deleteCustomer(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = DeleteCustomerSchema.parse(req.body);

  await prisma.$transaction(async (tx) => {
    const existing = await tx.customer.findFirst({ where: { id, ...activeWhere } });
    if (!existing) throw new NotFoundError("Customer");

    if (body.confirm_name.trim() !== existing.name) {
      throw new ValidationError(
        "Confirmation name does not match. Type the customer name exactly to delete."
      );
    }

    const deleted = await tx.customer.update({
      where: { id },
      data: { deleted_at: new Date() },
    });
    await writeAudit(tx, {
      action: "DELETE",
      entity_type: "Customer",
      entity_id: id,
      actor_id: req.user!.id,
      summary: `Deleted customer ${existing.name}`,
      before: existing,
      after: deleted,
    });

    emitEntityChanged("customer:changed", id);
    emitAuditChanged();
  });

  res.json({ success: true, data: { id } });
}
