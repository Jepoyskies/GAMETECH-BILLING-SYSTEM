import { Request, Response } from "express";
import { z } from "zod";
import prisma from "../../lib/prisma";
import { resolveDashboardDateRange, monthLabel, monthSpan } from "../../lib/utils";
import { getOptionId } from "../../lib/configOptions";
import { DashboardQuerySchema } from "../../lib/validators";
import ExcelJS from "exceljs";
import {
  pxToWidth,
  applyHeaderRow,
  applyDataRowStyle,
  addTitleRow,
  sendExcel,
} from "../../lib/excelExport";
import { renderBarChartToPng, renderPieChartToPng } from "../../lib/chartRenderer";
import type { BarSeries, PieSlice } from "../../lib/chartRenderer";
import logger from "../../lib/logger";

const MIN_DATE = new Date("1970-01-01T00:00:00.000Z");
const MAX_DATE = new Date("2999-12-31T23:59:59.999Z");

async function safeQuery<T>(promise: Promise<T>, fallback: T, context: string): Promise<T> {
  try {
    return await promise;
  } catch (error) {
    logger.error({ err: error, context }, "Query failed");
    return fallback;
  }
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function pngToBuffer(png: Uint8Array): any {
  const buf = Buffer.alloc(png.length);
  for (let i = 0; i < png.length; i++) buf[i] = png[i];
  return buf;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export async function exportDashboardExcel(req: Request, res: Response) {
  try {
    const { date_from, date_to, pie_mode } = DashboardQuerySchema.extend({
      pie_mode: z.enum(["internet_install", "cignal_play", "client_concerns"]).optional(),
    }).parse(req.query);
    const range = resolveDashboardDateRange(date_from, date_to);
    const lower = range.start ?? MIN_DATE;
    const upper = range.end ?? MAX_DATE;
    const periodLabel = range.label;

    const [installationTypeId, repairTypeId, concernsChatTypeId, doneStatusId, cancelledStatusId] = await Promise.all([
      getOptionId("TYPE", "DISPATCH", "Installation").catch(() => null),
      getOptionId("TYPE", "DISPATCH", "Repair").catch(() => null),
      getOptionId("CHAT_TYPE", "DISPATCH", "Concern").catch(() => null),
      getOptionId("STATUS", "DISPATCH", "Done").catch(() => null),
      getOptionId("STATUS", "DISPATCH", "Cancelled").catch(() => null),
    ]);

    const [totalDispatches, installs, repairs, concerns] = await Promise.all([
      safeQuery(prisma.dispatch.count({ where: { ...range.dateFilter, deleted_at: null } }), 0, "total"),
      safeQuery(prisma.dispatch.count({ where: { ...range.dateFilter, deleted_at: null, ...(installationTypeId ? { type_id: installationTypeId } : {}) } }), 0, "installs"),
      safeQuery(prisma.dispatch.count({ where: { ...range.dateFilter, deleted_at: null, ...(repairTypeId ? { type_id: repairTypeId } : {}) } }), 0, "repairs"),
      safeQuery(prisma.dispatch.count({ where: { ...range.dateFilter, deleted_at: null, ...(concernsChatTypeId ? { chat_type_id: concernsChatTypeId } : {}) } }), 0, "concerns"),
    ]);

    const forDispatch = await safeQuery(
      prisma.monitoringRecord.groupBy({
        by: ["tab_type"],
        where: {
          deleted_at: null,
          done_at: null,
          time_start: null,
          tab_type: { in: ["INTERNET_INSTALL", "CIGNAL_PLAY", "CLIENT_CONCERNS"] },
        },
        _count: { _all: true },
      }),
      [],
      "Failed to load for-dispatch counts"
    );
    const forDispatchMap = Object.fromEntries(forDispatch.map((p) => [p.tab_type, p._count._all]));
    const forDispatchTotal = (forDispatchMap["INTERNET_INSTALL"] ?? 0) + (forDispatchMap["CIGNAL_PLAY"] ?? 0) + (forDispatchMap["CLIENT_CONCERNS"] ?? 0);

    const [ongoing, closed, cancelled] = await Promise.all([
      safeQuery(prisma.monitoringRecord.count({ where: { deleted_at: null, time_start: { not: null }, done_at: null } }), 0, "ongoing"),
      safeQuery(
        doneStatusId
          ? prisma.dispatch.count({ where: { deleted_at: null, status_id: doneStatusId, ...(range.doneAtFilter.done_at ? { done_at: range.doneAtFilter.done_at } : {}) } })
          : Promise.resolve(0),
        0,
        "closed"
      ),
      safeQuery(
        cancelledStatusId
          ? prisma.dispatch.count({ where: { deleted_at: null, status_id: cancelledStatusId, ...(range.doneAtFilter.done_at ? { done_at: range.doneAtFilter.done_at } : {}) } })
          : Promise.resolve(0),
        0,
        "cancelled"
      ),
    ]);

    // ── Monitoring status breakdown (for pie chart) ──
    const monitoringStatusOptions = await safeQuery(
      prisma.configOption.findMany({ where: { list_type: "STATUS", module: "MONITORING" } }),
      [],
      "Failed to load monitoring status options"
    );
    const monitoringStatusLabelById = new Map(monitoringStatusOptions.map((o) => [o.id, o.label]));

    const tabFilter = pie_mode ? { tab_type: pie_mode.toUpperCase() as "INTERNET_INSTALL" | "CIGNAL_PLAY" | "CLIENT_CONCERNS" } : {};

    const monitoringBaseStatusCounts = await safeQuery(
      prisma.monitoringRecord.groupBy({
        by: ["status_id"],
        where: { deleted_at: null, ...range.dateFilter, ...tabFilter },
        _count: { _all: true },
      }),
      [],
      "Failed to load monitoring status counts"
    );

    const monitoringOverallStatus: Record<string, number> = {};
    for (const row of monitoringBaseStatusCounts) {
      const label = monitoringStatusLabelById.get(row.status_id) ?? "Unknown";
      monitoringOverallStatus[label] = (monitoringOverallStatus[label] ?? 0) + row._count._all;
    }

    const statusPieData: PieSlice[] = monitoringStatusOptions
      .filter((o) => (monitoringOverallStatus[o.label] ?? 0) > 0)
      .map((o) => ({
        label: o.label,
        value: monitoringOverallStatus[o.label] ?? 0,
        color: o.color ?? "#94a3b8",
      }));

    const pieTitle = pie_mode
      ? `${pie_mode === "internet_install" ? "Internet Install" : pie_mode === "cignal_play" ? "Cignal Play" : "Client Concerns"} Monitoring Status`
      : "Monitoring Status";

    const targets = await safeQuery(
      prisma.monthlyTarget.findMany({ orderBy: [{ year: "asc" }, { month: "asc" }] }),
      [],
      "targets"
    );
    const targetsWithActuals = await Promise.all(
      targets.map(async (t) => {
        const monthStart = new Date(Date.UTC(t.year, t.month - 1, 1));
        const monthEnd = new Date(Date.UTC(t.year, t.month, 1));
        const actual = await safeQuery(
          prisma.dispatch.count({
            where: {
              ...(installationTypeId ? { type_id: installationTypeId } : {}),
              ...(doneStatusId ? { status_id: doneStatusId } : {}),
              deleted_at: null,
              done_at: { gte: monthStart, lt: monthEnd },
            },
          }),
          0,
          `actuals for ${t.year}-${t.month}`
        );
        return {
          month: t.month,
          month_label: monthLabel(t.month),
          year: t.year,
          target: t.target,
          actual,
          remaining: Math.max(0, t.target - actual),
          percentage: t.target > 0 ? parseFloat(((actual / t.target) * 100).toFixed(2)) : 0,
        };
      })
    );

    // Staff stats
    const staffStats = await safeQuery(
      prisma.$queryRaw<{ technician_id: number; name: string; installs: bigint; repairs: bigint; target_per_day: number; target_per_month: number }[]>`
        SELECT t.id AS technician_id, t.name, t.target_per_day, t.target_per_month,
          COUNT(CASE WHEN d.type_id = ${installationTypeId} THEN 1 END) AS installs,
          COUNT(CASE WHEN d.type_id = ${repairTypeId} THEN 1 END) AS repairs
        FROM "Technician" t
        LEFT JOIN "DispatchTeam" dt ON dt.technician_id = t.id
        LEFT JOIN "Dispatch" d ON d.id = dt.dispatch_id AND d.deleted_at IS NULL AND d.done_at >= ${lower} AND d.done_at <= ${upper}
        WHERE t.deleted_at IS NULL
        GROUP BY t.id, t.name, t.target_per_day, t.target_per_month
        ORDER BY (COUNT(CASE WHEN d.type_id = ${installationTypeId} THEN 1 END) + COUNT(CASE WHEN d.type_id = ${repairTypeId} THEN 1 END)) DESC
      `,
      [],
      "staff stats"
    );
    const monthCount = range.start
      ? monthSpan(range.start, range.end ?? new Date())
      : 1;
    const workingDays = monthCount * 26;
    const enrichedStaff = staffStats.map((tech, idx) => {
      const installs = Number(tech.installs);
      const repairs = Number(tech.repairs);
      const total = installs + repairs;
      const scaledTarget = (tech.target_per_month ?? 0) * monthCount;
      return {
        technician: tech.name,
        installs,
        repairs,
        total,
        target_per_day: tech.target_per_day ?? 0,
        target_per_month: tech.target_per_month ?? 0,
        percentage: scaledTarget > 0 ? parseFloat(((total / scaledTarget) * 100).toFixed(2)) : null,
        per_day: workingDays > 0 ? parseFloat((total / workingDays).toFixed(2)) : 0,
        rank: idx + 1,
      };
    });

    // Admin stats
    const adminStats = await safeQuery(
      prisma.$queryRaw<{ csr_id: number; name: string; total_records: bigint; dispatch_handled: bigint; dispatch_closed: bigint; dispatch_cancelled: bigint; concerns_handled: bigint; concerns_closed: bigint; concerns_cancelled: bigint }[]>`
        WITH records AS (
          SELECT
            d.csr_id,
            CASE
              WHEN d.type_id IN (${installationTypeId}, ${repairTypeId})
                AND (d.chat_type_id IS NULL OR d.chat_type_id != ${concernsChatTypeId}) THEN 'install_repair'
              WHEN d.chat_type_id = ${concernsChatTypeId} THEN 'concern'
              ELSE 'other'
            END AS category,
            d.date,
            d.done_at,
            d.status_id,
            'dispatch' AS source
          FROM "Dispatch" d
          WHERE d.deleted_at IS NULL

          UNION ALL

          SELECT
            m.csr_id,
            CASE
              WHEN m.tab_type IN ('INTERNET_INSTALL', 'CIGNAL_PLAY') THEN 'install_repair'
              WHEN m.tab_type = 'CLIENT_CONCERNS' THEN 'concern'
              ELSE 'other'
            END AS category,
            m.date,
            m.done_at,
            NULL AS status_id,
            'monitoring' AS source
          FROM "MonitoringRecord" m
          WHERE m.deleted_at IS NULL
            AND NOT EXISTS (
              SELECT 1 FROM "Dispatch" d2
              WHERE d2.monitoring_id = m.id
            )
        )
        SELECT
          c.id AS csr_id,
          c.name,
          COUNT(*) FILTER (WHERE r.date >= ${lower} AND r.date <= ${upper}) AS total_records,
          COUNT(*) FILTER (WHERE r.category = 'install_repair' AND r.date >= ${lower} AND r.date <= ${upper}) AS dispatch_handled,
          COUNT(*) FILTER (WHERE r.category = 'install_repair' AND r.status_id = ${doneStatusId} AND r.done_at >= ${lower} AND r.done_at <= ${upper}) AS dispatch_closed,
          COUNT(*) FILTER (WHERE r.category = 'install_repair' AND r.status_id = ${cancelledStatusId} AND r.date >= ${lower} AND r.date <= ${upper}) AS dispatch_cancelled,
          COUNT(*) FILTER (WHERE r.category = 'concern' AND r.date >= ${lower} AND r.date <= ${upper}) AS concerns_handled,
          COUNT(*) FILTER (WHERE r.category = 'concern' AND r.source = 'dispatch' AND r.status_id = ${doneStatusId} AND r.done_at >= ${lower} AND r.done_at <= ${upper}) AS concerns_closed,
          COUNT(*) FILTER (WHERE r.category = 'concern' AND r.source = 'dispatch' AND r.status_id = ${cancelledStatusId} AND r.date >= ${lower} AND r.date <= ${upper}) AS concerns_cancelled
        FROM "CSR" c
        LEFT JOIN records r ON r.csr_id = c.id
        WHERE c.deleted_at IS NULL
        GROUP BY c.id, c.name
        ORDER BY c.name ASC
      `,
      [],
      "admin stats"
    );
    const enrichedAdmin = adminStats.map((row) => {
      const totalRecords = Number(row.total_records);
      const dh = Number(row.dispatch_handled);
      const dc = Number(row.dispatch_closed);
      const dCancelled = Number(row.dispatch_cancelled);
      const ch = Number(row.concerns_handled);
      const cc = Number(row.concerns_closed);
      const cCancelled = Number(row.concerns_cancelled);
      const dispatchEffectiveBase = dh - dCancelled;
      const concernsEffectiveBase = ch - cCancelled;
      return {
        csr: row.name,
        total_records: totalRecords,
        dispatch_handled: dh,
        dispatch_closed: dc,
        dispatch_cancelled: dCancelled,
        dispatch_close_rate: dispatchEffectiveBase > 0 ? parseFloat(((dc / dispatchEffectiveBase) * 100).toFixed(2)) : 0,
        concerns_handled: ch,
        concerns_closed: cc,
        concerns_cancelled: cCancelled,
        concerns_close_rate: concernsEffectiveBase > 0 ? parseFloat(((cc / concernsEffectiveBase) * 100).toFixed(2)) : 0,
        rank: 0,
      };
    });
    enrichedAdmin.sort((a, b) => b.total_records - a.total_records || a.csr.localeCompare(b.csr));
    enrichedAdmin.forEach((row, idx) => {
      row.rank = idx + 1;
    });

    const workbook = new ExcelJS.Workbook();
    workbook.creator = "Dispatch Monitoring System";

    // ═══════════════════════════════════════════════
    // Sheet 1: Summary
    // ═══════════════════════════════════════════════
    const summarySheet = workbook.addWorksheet("Summary");
    const summaryCols = [
      { header: "Metric", key: "metric", width: pxToWidth(180) },
      { header: "Value", key: "value", width: pxToWidth(120) },
    ];
    summarySheet.columns = summaryCols;

    addTitleRow(summarySheet, `Dashboard Summary — ${periodLabel}`, 2);

    const summaryData = [
      { metric: "Total Dispatches", value: totalDispatches },
      { metric: "Installations", value: installs },
      { metric: "Repairs", value: repairs },
      { metric: "Concerns", value: concerns },
      { metric: "For Dispatch", value: forDispatchTotal },
      { metric: "Ongoing Monitoring", value: ongoing },
      { metric: "Closed", value: closed },
      { metric: "Cancelled", value: cancelled },
    ];
    summaryData.forEach((row) => {
      const r = summarySheet.addRow([row.metric, row.value]);
      applyDataRowStyle(r);
    });

    // ── Pie chart for status breakdown ──
    if (statusPieData.length > 0) {
      const pieResult = await renderPieChartToPng(statusPieData, pieTitle);
      const pieImgId = workbook.addImage({ buffer: pngToBuffer(pieResult.png), extension: "png" });
      const pieRow = summarySheet.rowCount + 2;
      summarySheet.addImage(pieImgId, {
        tl: { col: 0, row: pieRow - 1 },
        ext: { width: pieResult.width, height: pieResult.height },
      });
    }

    // ═══════════════════════════════════════════════
    // Sheet 2: Monthly Targets
    // ═══════════════════════════════════════════════
    const targetSheet = workbook.addWorksheet("Monthly Targets");
    const targetCols = [
      { header: "Month", key: "month", width: pxToWidth(100) },
      { header: "Year", key: "year", width: pxToWidth(80) },
      { header: "Target", key: "target", width: pxToWidth(100) },
      { header: "Actual", key: "actual", width: pxToWidth(100) },
      { header: "Remaining", key: "remaining", width: pxToWidth(100) },
      { header: "Percentage", key: "percentage", width: pxToWidth(100) },
    ];
    targetSheet.columns = targetCols;

    addTitleRow(targetSheet, `Monthly Install Targets — ${periodLabel}`, targetCols.length);
    applyHeaderRow(targetSheet, 2, targetCols);

    targetsWithActuals.forEach((t) => {
      const r = targetSheet.addRow([t.month_label, t.year, t.target, t.actual, t.remaining, `${t.percentage}%`]);
      applyDataRowStyle(r);
    });

    if (targetsWithActuals.length > 0) {
      const barLabels = targetsWithActuals.map((t) => `${t.month_label.slice(0, 3)} ${t.year}`);
      const barSeries: BarSeries[] = [
        { label: "Target", values: targetsWithActuals.map((t) => t.target), color: "#94a3b8" },
        { label: "Actual", values: targetsWithActuals.map((t) => t.actual), color: "#3533cd" },
      ];
      const barPng = await renderBarChartToPng(barLabels, barSeries, `Monthly Install Targets — ${periodLabel}`);
      const barImgId = workbook.addImage({ buffer: pngToBuffer(barPng), extension: "png" });
      const barRow = targetSheet.rowCount + 2;
      targetSheet.addImage(barImgId, {
        tl: { col: 0, row: barRow - 1 },
        ext: { width: 640, height: 360 },
      });
    }

    // ═══════════════════════════════════════════════
    // Sheet 3: Technicals (Staff)
    // ═══════════════════════════════════════════════
    const staffSheet = workbook.addWorksheet("Technicals (Staff)");
    const staffCols = [
      { header: "Rank", key: "rank", width: pxToWidth(50) },
      { header: "Technician", key: "technician", width: pxToWidth(180) },
      { header: "Installs", key: "installs", width: pxToWidth(80) },
      { header: "Repairs", key: "repairs", width: pxToWidth(80) },
      { header: "Total", key: "total", width: pxToWidth(80) },
      { header: "Target/Day", key: "target_per_day", width: pxToWidth(90) },
      { header: "Target/Month", key: "target_per_month", width: pxToWidth(100) },
      { header: "% of Product", key: "percentage", width: pxToWidth(100) },
      { header: "Per Day (avg)", key: "per_day", width: pxToWidth(100) },
    ];
    staffSheet.columns = staffCols;

    addTitleRow(staffSheet, `Technician Statistics — ${periodLabel}`, staffCols.length);
    applyHeaderRow(staffSheet, 2, staffCols);

    enrichedStaff.forEach((s) => {
      const r = staffSheet.addRow([s.rank, s.technician, s.installs, s.repairs, s.total, s.target_per_day, s.target_per_month, s.percentage !== null ? `${s.percentage}%` : "—", s.per_day]);
      applyDataRowStyle(r);
    });

    // ═══════════════════════════════════════════════
    // Sheet 4: Admin Stats
    // ═══════════════════════════════════════════════
    const adminSheet = workbook.addWorksheet("Admin Stats");
    const adminCols = [
      { header: "Rank", key: "rank", width: pxToWidth(50) },
      { header: "CSR", key: "csr", width: pxToWidth(180) },
      { header: "Assigned", key: "total_records", width: pxToWidth(110) },
      { header: "Dispatch Handled", key: "dispatch_handled", width: pxToWidth(130) },
      { header: "Dispatch Closed", key: "dispatch_closed", width: pxToWidth(120) },
      { header: "Close Rate", key: "dispatch_close_rate", width: pxToWidth(100) },
      { header: "Concerns Handled", key: "concerns_handled", width: pxToWidth(130) },
      { header: "Concerns Closed", key: "concerns_closed", width: pxToWidth(120) },
      { header: "Concern Close Rate", key: "concerns_close_rate", width: pxToWidth(120) },
    ];
    adminSheet.columns = adminCols;

    addTitleRow(adminSheet, `Admin Statistics — ${periodLabel}`, adminCols.length);
    applyHeaderRow(adminSheet, 2, adminCols);

    enrichedAdmin.forEach((a) => {
      const r = adminSheet.addRow([a.rank, a.csr, a.total_records, a.dispatch_handled, a.dispatch_closed, `${a.dispatch_close_rate}%`, a.concerns_handled, a.concerns_closed, `${a.concerns_close_rate}%`]);
      applyDataRowStyle(r);
    });

    const filename = `dashboard_${periodLabel.replace(/[^a-zA-Z0-9]/g, "_").toLowerCase()}.xlsx`;
    sendExcel(res, workbook, filename);
  } catch (error) {
    logger.error({ err: error }, "Dashboard export error");
    res.status(500).json({ success: false, error: "Unable to export dashboard" });
  }
}
