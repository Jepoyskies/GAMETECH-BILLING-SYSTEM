import { Request, Response } from "express";
import { Prisma } from "@prisma/client";
import prisma from "../../lib/prisma";
import { AuditQuerySchema } from "../../lib/validators";
import { buildDateRangeFilter } from "../../lib/queryFilters";
import {
  assertExportRangeAllowed,
  sendCsv,
  EXPORT_MAX_ROWS,
  fmtDateTime,
  monthToRange,
} from "../../lib/csvExport";
import { BadRequestError } from "../../lib/errors";
import ExcelJS from "exceljs";
import {
  pxToWidth,
  applyHeaderRow,
  applyDataRowStyle,
  addTitleRow,
  sendExcel,
} from "../../lib/excelExport";

const EXPORT_MONTHS_LOOKBACK = 12;

function buildAuditWhere(query: ReturnType<typeof AuditQuerySchema.parse>) {
  const { action, entity_type, entity_id, actor, date_from, date_to } = query;
  const dateRange = buildDateRangeFilter(date_from, date_to);

  const where: Prisma.AuditLogWhereInput = {
    ...(action && { action }),
    ...(entity_type && { entity_type }),
    ...(entity_id && { entity_id }),
    ...(actor && { actor_id: actor }),
    ...(dateRange.date && { created_at: dateRange.date }),
  };
  return where;
}

export async function listAuditExportMonths(req: Request, res: Response) {
  const query = AuditQuerySchema.parse(req.query);
  const { action, entity_type, entity_id, actor } = query;

  const lookbackCutoff = new Date();
  lookbackCutoff.setMonth(lookbackCutoff.getMonth() - EXPORT_MONTHS_LOOKBACK);

  const where: Prisma.AuditLogWhereInput = {
    created_at: { gte: lookbackCutoff },
    ...(action && { action }),
    ...(entity_type && { entity_type }),
    ...(entity_id && { entity_id }),
    ...(actor && { actor_id: actor }),
  };

  const dates = await prisma.auditLog.findMany({
    where,
    select: { created_at: true },
  });

  const months = [
    ...new Set(
      dates.map((l) => {
        const dt = l.created_at;
        return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, "0")}`;
      })
    ),
  ].sort().reverse();

  res.json({ success: true, data: months });
}

// ── CSV export ────────────────────────────────────────────────────────────

export async function exportAuditLogs(req: Request, res: Response) {
  const monthParam = typeof req.query.month === "string" ? req.query.month : undefined;
  const resolvedRange = monthParam ? monthToRange(monthParam) : undefined;

  const query = AuditQuerySchema.parse({
    ...req.query,
    ...(resolvedRange ?? {}),
  });
  const { date_from, date_to } = query;

  assertExportRangeAllowed(date_from, date_to);

  const where = buildAuditWhere(query);

  const total = await prisma.auditLog.count({ where });
  if (total > EXPORT_MAX_ROWS) {
    throw new BadRequestError(
      `This range has ${total} records, which exceeds the export limit of ${EXPORT_MAX_ROWS}. Narrow your date range.`
    );
  }

  const logs = await prisma.auditLog.findMany({
    where,
    include: { actor: { select: { id: true, name: true } } },
    orderBy: { created_at: "desc" },
  });

  const headers = ["ID", "When", "Action", "Entity Type", "Entity ID", "Performed By", "Summary"];
  const rows = logs.map((l) => [
    l.id,
    l.created_at.toISOString(),
    l.action,
    l.entity_type,
    l.entity_id,
    l.actor?.name ?? `CSR #${l.actor_id}`,
    l.summary ?? "",
  ]);

  sendCsv(res, `audit-log_${date_from}_to_${date_to}.csv`, headers, rows);
}

// ── Excel export ──────────────────────────────────────────────────────────

export async function exportAuditLogsExcel(req: Request, res: Response) {
  const monthParam = typeof req.query.month === "string" ? req.query.month : undefined;
  const resolvedRange = monthParam ? monthToRange(monthParam) : undefined;

  const query = AuditQuerySchema.parse({
    ...req.query,
    ...(resolvedRange ?? {}),
  });
  const { date_from, date_to } = query;

  assertExportRangeAllowed(date_from, date_to);

  const where = buildAuditWhere(query);

  const total = await prisma.auditLog.count({ where });
  if (total > EXPORT_MAX_ROWS) {
    throw new BadRequestError(
      `This range has ${total} records, which exceeds the export limit of ${EXPORT_MAX_ROWS}. Narrow your date range.`
    );
  }

  const logs = await prisma.auditLog.findMany({
    where,
    include: { actor: { select: { id: true, name: true } } },
    orderBy: { created_at: "desc" },
  });

  const dateLabel = monthParam
    ? (() => {
        const [y, m] = monthParam.split("-").map(Number);
        const d = new Date(Date.UTC(y, m - 1, 1));
        return d.toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
      })()
    : `${fmtDateTime(new Date(date_from!))} — ${fmtDateTime(new Date(date_to!))}`;

  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("Audit Logs");

  const columnDefs = [
    { header: "ID", key: "id", width: pxToWidth(70) },
    { header: "When", key: "when", width: pxToWidth(245) },
    { header: "Action", key: "action", width: pxToWidth(140) },
    { header: "Entity Type", key: "entityType", width: pxToWidth(160) },
    { header: "Entity ID", key: "entityId", width: pxToWidth(100) },
    { header: "Performed By", key: "performedBy", width: pxToWidth(165) },
    { header: "Summary", key: "summary", width: pxToWidth(500) },
  ];

  sheet.columns = columnDefs;

  addTitleRow(sheet, `Audit Logs — ${dateLabel}`, columnDefs.length);

  applyHeaderRow(sheet, 2, columnDefs);

  logs.forEach((l) => {
    const rowData = [
      l.id,
      fmtDateTime(l.created_at),
      l.action,
      l.entity_type,
      l.entity_id,
      l.actor?.name ?? `CSR #${l.actor_id}`,
      l.summary ?? "",
    ];

    const row = sheet.addRow(rowData);
    applyDataRowStyle(row);
  });

  sendExcel(res, workbook, `audit-log_${date_from}_to_${date_to}.xlsx`);
}
