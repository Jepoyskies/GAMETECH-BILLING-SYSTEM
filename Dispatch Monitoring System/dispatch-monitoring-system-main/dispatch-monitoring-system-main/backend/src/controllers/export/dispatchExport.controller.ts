import { Request, Response } from "express";
import prisma from "../../lib/prisma";
import { csrPublicSelect } from "../../lib/select";
import { DispatchQuerySchema } from "../../lib/validators";
import {
  buildDateRangeFilter,
  buildTextContainsFilter,
  buildTeamFilter,
} from "../../lib/queryFilters";
import {
  assertExportRangeAllowed,
  sendCsv,
  EXPORT_MAX_ROWS,
  fmtDateTime,
  fmtDuration,
  monthToRange,
} from "../../lib/csvExport";
import { BadRequestError as ExportTooLargeError } from "../../lib/errors";
import ExcelJS from "exceljs";
import {
  pxToWidth,
  applyHeaderRow,
  applyDataRowStyle,
  addTitleRow,
  sendExcel,
} from "../../lib/excelExport";

const EXPORT_MONTHS_LOOKBACK = 12;

function buildDispatchWhere(query: ReturnType<typeof DispatchQuerySchema.parse>) {
  const {
    status_id, type_id, source_tab, chat_type_id,
    csr, client, sales_agent, teams,
    date_from, date_to,
  } = query;

  const clientFilter = buildTextContainsFilter(client);
  const salesAgentFilter = buildTextContainsFilter(sales_agent);
  const teamFilter = buildTeamFilter(teams);

  const where: Record<string, unknown> = {
    deleted_at: null,
    ...(source_tab && { source_tab }),
    ...(csr && { csr_id: csr }),
    ...(clientFilter && { client: clientFilter }),
    ...(salesAgentFilter && { sales_agent: salesAgentFilter }),
    ...buildDateRangeFilter(date_from, date_to),
    ...(teamFilter ?? {}),
  };
  if (status_id) where.status_id = status_id;
  if (type_id) where.type_id = type_id;
  if (chat_type_id) where.chat_type_id = chat_type_id;
  return where;
}

export async function listDispatchExportMonths(req: Request, res: Response) {
  const query = DispatchQuerySchema.parse(req.query);
  const { status_id, type_id, source_tab, chat_type_id, csr, client, sales_agent, teams } = query;

  const clientFilter = buildTextContainsFilter(client);
  const salesAgentFilter = buildTextContainsFilter(sales_agent);
  const teamFilter = buildTeamFilter(teams);

  const lookbackCutoff = new Date();
  lookbackCutoff.setMonth(lookbackCutoff.getMonth() - EXPORT_MONTHS_LOOKBACK);

  const where: Record<string, unknown> = {
    deleted_at: null,
    date: { gte: lookbackCutoff },
    ...(source_tab && { source_tab }),
    ...(csr && { csr_id: csr }),
    ...(clientFilter && { client: clientFilter }),
    ...(salesAgentFilter && { sales_agent: salesAgentFilter }),
    ...(teamFilter ?? {}),
  };
  if (status_id) where.status_id = status_id;
  if (type_id) where.type_id = type_id;
  if (chat_type_id) where.chat_type_id = chat_type_id;

  const dates = await prisma.dispatch.findMany({
    where,
    select: { date: true },
  });

  const months = [
    ...new Set(
      dates.map((d) => {
        const dt = d.date;
        return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, "0")}`;
      })
    ),
  ].sort().reverse();

  res.json({ success: true, data: months });
}

// ── CSV export ────────────────────────────────────────────────────────────

export async function exportDispatches(req: Request, res: Response) {
  const monthParam = typeof req.query.month === "string" ? req.query.month : undefined;
  const resolvedRange = monthParam ? monthToRange(monthParam) : undefined;

  const query = DispatchQuerySchema.parse({
    ...req.query,
    ...(resolvedRange ?? {}),
  });
  const { date_from, date_to } = query;

  assertExportRangeAllowed(date_from, date_to);

  const where = buildDispatchWhere(query);

  const total = await prisma.dispatch.count({ where });
  if (total > EXPORT_MAX_ROWS) {
    throw new ExportTooLargeError(
      `This range has ${total} records, which exceeds the export limit of ${EXPORT_MAX_ROWS}. Narrow your date range.`
    );
  }

  const records = await prisma.dispatch.findMany({
    where,
    include: {
      statusOption: true,
      typeOption: true,
      chatTypeOption: true,
      teams: { include: { technician: true } },
      csr: { select: csrPublicSelect },
      monitoring: { include: { jobDetail: true } },
    },
    orderBy: [{ date: "desc" }, { created_at: "desc" }],
  });

  const headers = [
    "ID", "Status", "Date Created", "Done At", "Turnaround", "Client", "Concern",
    "Type", "Chat Type", "Source", "Time Start", "Time Done", "Duration",
    "Team", "CSR", "Sales Agent", "Address", "Contact", "Ticket Number", "Remarks",
    "Schedule Date", "Schedule Time", "Barangay/City", "Account No.", "Job Order",
    "Email Address", "NAP/Port", "Cable Length Used", "NAP Reading", "Pole Number",
    "Plan/Package", "ONT/Modem SN", "Signal Level", "Facility", "House Reading",
    "Special Instruction", "Technician Remarks", "Acknowledged By",
  ];

  const rows = records.map((d) => {
    const doneAt = d.monitoring?.done_at ?? null;
    let turnaround = "";
    if (doneAt) {
      const diffMinutes = Math.round((doneAt.getTime() - d.date.getTime()) / 60000);
      if (diffMinutes >= 0) turnaround = fmtDuration(diffMinutes);
    }
    const jd = d.monitoring?.jobDetail;

    return [
      d.id,
      d.statusOption?.label ?? "",
      d.date.toISOString(),
      doneAt ? doneAt.toISOString() : "",
      turnaround,
      d.client,
      d.concern,
      d.typeOption?.label ?? "",
      d.chatTypeOption?.label ?? "",
      d.source_tab,
      d.time_start ? d.time_start.toISOString() : "",
      d.time_accomplish ? d.time_accomplish.toISOString() : "",
      fmtDuration(d.duration),
      d.teams.map((t) => t.technician.name).join("; "),
      d.csr?.name ?? "",
      d.sales_agent,
      d.address,
      d.contact_number,
      d.ticket_number ?? "",
      d.remarks ?? "",
      jd?.schedule_date ? jd.schedule_date.toISOString() : "",
      jd?.schedule_time ?? "",
      jd?.barangay_city ?? "",
      jd?.account_no ?? "",
      jd?.job_order ?? "",
      jd?.email_address ?? "",
      jd?.nap_port ?? "",
      jd?.cable_length ?? "",
      jd?.nap_reading ?? "",
      jd?.pole_number ?? "",
      jd?.plan_package ?? "",
      jd?.ont_modem_sn ?? "",
      jd?.signal_level ?? "",
      jd?.facility ?? "",
      jd?.house_reading ?? "",
      jd?.special_instruction ?? "",
      jd?.technician_remarks ?? "",
      jd?.acknowledged_by ?? "",
    ];
  });

  sendCsv(res, `dispatch-log_${date_from}_to_${date_to}.csv`, headers, rows);
}

// ── Excel export ──────────────────────────────────────────────────────────

export async function exportDispatchesExcel(req: Request, res: Response) {
  const monthParam = typeof req.query.month === "string" ? req.query.month : undefined;
  const resolvedRange = monthParam ? monthToRange(monthParam) : undefined;

  const query = DispatchQuerySchema.parse({
    ...req.query,
    ...(resolvedRange ?? {}),
  });
  const { date_from, date_to } = query;

  assertExportRangeAllowed(date_from, date_to);

  const where = buildDispatchWhere(query);

  const total = await prisma.dispatch.count({ where });
  if (total > EXPORT_MAX_ROWS) {
    throw new ExportTooLargeError(
      `This range has ${total} records, which exceeds the export limit of ${EXPORT_MAX_ROWS}. Narrow your date range.`
    );
  }

  const records = await prisma.dispatch.findMany({
    where,
    include: {
      statusOption: true,
      typeOption: true,
      chatTypeOption: true,
      teams: { include: { technician: true } },
      csr: { select: csrPublicSelect },
      monitoring: { include: { jobDetail: true } },
    },
    orderBy: [{ date: "desc" }, { created_at: "desc" }],
  });

  const dateLabel = monthParam
    ? (() => {
        const [y, m] = monthParam.split("-").map(Number);
        const d = new Date(Date.UTC(y, m - 1, 1));
        return d.toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
      })()
    : `${fmtDateTime(new Date(date_from!))} — ${fmtDateTime(new Date(date_to!))}`;

  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("Dispatch Logs");

  const columnDefs = [
    // ── Record Info ──
    { header: "ID", key: "id", width: pxToWidth(60) },
    { header: "Ticket No.", key: "ticketNumber", width: pxToWidth(140) },
    { header: "Status", key: "status", width: pxToWidth(130) },
    { header: "Date Created", key: "date", width: pxToWidth(150) },
    { header: "Date Completed", key: "done_at", width: pxToWidth(150) },
    { header: "Turnaround", key: "turnaround", width: pxToWidth(105) },
    // ── Customer ──
    { header: "Client", key: "client", width: pxToWidth(310) },
    { header: "Account No.", key: "accountNo", width: pxToWidth(130) },
    { header: "Address", key: "address", width: pxToWidth(420) },
    { header: "Barangay/City", key: "barangayCity", width: pxToWidth(350) },
    { header: "Contact", key: "contact", width: pxToWidth(190) },
    { header: "Email Address", key: "emailAddress", width: pxToWidth(205) },
    // ── Service ──
    { header: "Concern", key: "concern", width: pxToWidth(320) },
    { header: "Type", key: "type", width: pxToWidth(160) },
    { header: "Chat Type", key: "chatType", width: pxToWidth(125) },
    { header: "Source", key: "source", width: pxToWidth(160) },
    { header: "Service Start", key: "timeStart", width: pxToWidth(165) },
    { header: "Service End", key: "timeDone", width: pxToWidth(165) },
    { header: "Service Duration", key: "duration", width: pxToWidth(140) },
    // ── Assignment ──
    { header: "Team", key: "team", width: pxToWidth(460) },
    { header: "CSR", key: "csr", width: pxToWidth(185) },
    { header: "Sales Agent", key: "salesAgent", width: pxToWidth(190) },
    // ── Job Site / Tech Details ──
    { header: "NAP/Port", key: "napPort", width: pxToWidth(120) },
    { header: "Cable Length Used", key: "cableLength", width: pxToWidth(150) },
    { header: "NAP Reading", key: "napReading", width: pxToWidth(130) },
    { header: "Pole Number", key: "poleNumber", width: pxToWidth(120) },
    { header: "Plan/Package", key: "planPackage", width: pxToWidth(170) },
    { header: "ONT/Modem SN", key: "ontModemSn", width: pxToWidth(150) },
    { header: "Signal Level", key: "signalLevel", width: pxToWidth(120) },
    { header: "Facility", key: "facility", width: pxToWidth(150) },
    { header: "House Reading", key: "houseReading", width: pxToWidth(150) },
    { header: "Special Instruction", key: "specialInstruction", width: pxToWidth(230) },
    { header: "Technician Remarks", key: "technicianRemarks", width: pxToWidth(230) },
    { header: "Acknowledged By", key: "acknowledgedBy", width: pxToWidth(310) },
    // ── Notes & Scheduling ──
    { header: "Remarks", key: "remarks", width: pxToWidth(230) },
    { header: "Schedule Date", key: "scheduleDate", width: pxToWidth(140) },
    { header: "Schedule Time", key: "scheduleTime", width: pxToWidth(140) },
  ];

  sheet.columns = columnDefs;

  addTitleRow(sheet, `Dispatch Logs — ${dateLabel}`, columnDefs.length);

  applyHeaderRow(sheet, 2, columnDefs);

  records.forEach((d) => {
    const doneAt = d.monitoring?.done_at ?? null;
    let turnaround = "";
    if (doneAt) {
      const diffMinutes = Math.round((doneAt.getTime() - d.date.getTime()) / 60000);
      if (diffMinutes >= 0) turnaround = fmtDuration(diffMinutes);
    }
    const jd = d.monitoring?.jobDetail;

    const rowData = [
      d.id,
      d.ticket_number ?? "",
      d.statusOption?.label ?? "",
      fmtDateTime(d.date),
      fmtDateTime(doneAt),
      turnaround,
      d.client,
      jd?.account_no ?? "",
      d.address,
      jd?.barangay_city ?? "",
      d.contact_number,
      jd?.email_address ?? "",
      d.concern,
      d.typeOption?.label ?? "",
      d.chatTypeOption?.label ?? "",
      d.source_tab,
      fmtDateTime(d.time_start),
      fmtDateTime(d.time_accomplish),
      fmtDuration(d.duration),
      d.teams.map((t) => t.technician.name).join("; "),
      d.csr?.name ?? "",
      d.sales_agent,
      jd?.nap_port ?? "",
      jd?.cable_length ?? "",
      jd?.nap_reading ?? "",
      jd?.pole_number ?? "",
      jd?.plan_package ?? "",
      jd?.ont_modem_sn ?? "",
      jd?.signal_level ?? "",
      jd?.facility ?? "",
      jd?.house_reading ?? "",
      jd?.special_instruction ?? "",
      jd?.technician_remarks ?? "",
      jd?.acknowledged_by ?? "",
      d.remarks ?? "",
      jd?.schedule_date ? jd.schedule_date.toLocaleDateString("en-US") : "",
      jd?.schedule_time ?? "",
    ];

    const row = sheet.addRow(rowData);
    applyDataRowStyle(row);
  });

  sendExcel(res, workbook, `dispatch-log_${date_from}_to_${date_to}.xlsx`);
}
