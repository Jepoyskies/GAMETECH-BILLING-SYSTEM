import { Request, Response } from "express";
import prisma from "../lib/prisma";
import {
  resolveDashboardDateRange,
  monthSpan,
  monthLabel,
  parseIdParam,
} from "../lib/utils";
import { NotFoundError } from "../lib/errors";
import { getOptionId } from "../lib/configOptions";
import { writeAudit } from "../lib/audit";
import { DashboardQuerySchema, MonthlyTargetSchema } from "../lib/validators";
import { emitAuditChanged, emitEntityChanged } from "../lib/socket";
import logger from "../lib/logger";

const MIN_DATE = new Date("1970-01-01T00:00:00.000Z");
const MAX_DATE = new Date("2999-12-31T23:59:59.999Z");

function sendErrorResponse(res: Response, error: unknown, fallbackMessage: string) {
  if (error instanceof Error && "statusCode" in error) {
    const statusCode = Number((error as { statusCode?: number }).statusCode ?? 500);
    res.status(statusCode).json({
      success: false,
      error: error.message,
    });
    return;
  }

  logger.error({ err: error }, fallbackMessage);
  res.status(500).json({
    success: false,
    error: fallbackMessage,
  });
}

async function getOptionIdOrNull(
  listType: "TYPE" | "CHAT_TYPE" | "STATUS",
  module: "DISPATCH" | "MONITORING",
  label: string
): Promise<number | null> {
  try {
    return await getOptionId(listType, module, label);
  } catch (error) {
    logger.warn({ label, listType, module, error }, `Dashboard config option missing`);
    return null;
  }
}

async function safeQuery<T>(promise: Promise<T>, fallback: T, context: string): Promise<T> {
  try {
    return await promise;
  } catch (error) {
    logger.error({ err: error, context }, "Query failed");
    return fallback;
  }
}

export async function getStats(req: Request, res: Response) {
  try {
    const { date_from, date_to } = DashboardQuerySchema.parse(req.query);
    const range = resolveDashboardDateRange(date_from, date_to);
    const now = new Date();

    const [installationTypeId, repairTypeId, concernsChatTypeId] = await Promise.all([
      getOptionIdOrNull("TYPE", "DISPATCH", "Installation"),
      getOptionIdOrNull("TYPE", "DISPATCH", "Repair"),
      getOptionIdOrNull("CHAT_TYPE", "DISPATCH", "Concern"),
    ]);

    const warnings: string[] = [];
    if (!installationTypeId) warnings.push("Installation type option unavailable; installation counts may be incomplete.");
    if (!repairTypeId) warnings.push("Repair type option unavailable; repair counts may be incomplete.");
    if (!concernsChatTypeId) warnings.push("Concern chat type option unavailable; concern counts may be incomplete.");

    const statusOptions = await safeQuery(
      prisma.configOption.findMany({ where: { list_type: "STATUS", module: "DISPATCH" } }),
      [],
      "Failed to load dashboard status options"
    );
    const doneStatusId = statusOptions.find((o) => o.label === "Done")?.id ?? null;
    const cancelledStatusId = statusOptions.find((o) => o.label === "Cancelled")?.id ?? null;

    const [
      totalDispatches, installs, repairs, concerns,
      pendingMonitoring,
      ongoingDispatches,
      closedCount, cancelledCount,
      installForDispatch, installOngoing,
      repairForDispatch, repairOngoing,
    ] = await Promise.all([
      safeQuery(prisma.dispatch.count({ where: { ...range.dateFilter, deleted_at: null } }), 0, "Failed to load total dispatch count"),
      safeQuery(prisma.dispatch.count({ where: { ...range.dateFilter, deleted_at: null, ...(installationTypeId ? { type_id: installationTypeId } : {}) } }), 0, "Failed to load installation count"),
      safeQuery(prisma.dispatch.count({ where: { ...range.dateFilter, deleted_at: null, ...(repairTypeId ? { type_id: repairTypeId } : {}) } }), 0, "Failed to load repair count"),
      safeQuery(prisma.dispatch.count({ where: { ...range.dateFilter, deleted_at: null, ...(concernsChatTypeId ? { chat_type_id: concernsChatTypeId } : {}) } }), 0, "Failed to load concern count"),
      safeQuery(
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
        "Failed to load pending monitoring counts"
      ),

      safeQuery(
        prisma.monitoringRecord.count({
          where: {
            deleted_at: null,
            time_start: { not: null },
            done_at: null,
          },
        }),
        0,
        "Failed to load ongoing monitoring count"
      ),

      safeQuery(
        (async () => {
          if (!doneStatusId) return 0;
          const doneFilter = range.doneAtFilter.done_at
            ? { done_at: range.doneAtFilter.done_at }
            : {};
          return prisma.dispatch.count({
            where: { deleted_at: null, status_id: doneStatusId, ...doneFilter },
          });
        })(),
        0,
        "Failed to load closed dispatch count"
      ),

      safeQuery(
        (async () => {
          if (!cancelledStatusId) return 0;
          const doneFilter = range.doneAtFilter.done_at
            ? { done_at: range.doneAtFilter.done_at }
            : {};
          return prisma.dispatch.count({
            where: { deleted_at: null, status_id: cancelledStatusId, ...doneFilter },
          });
        })(),
        0,
        "Failed to load cancelled dispatch count"
      ),

      safeQuery(
        (async () => {
          if (!installationTypeId) return 0;
          return prisma.monitoringRecord.count({
            where: {
              deleted_at: null,
              done_at: null,
              time_start: null,
              type_id: installationTypeId,
            },
          });
        })(),
        0,
        "Failed to load install for-dispatch count"
      ),

      safeQuery(
        (async () => {
          if (!installationTypeId) return 0;
          return prisma.monitoringRecord.count({
            where: {
              deleted_at: null,
              time_start: { not: null },
              done_at: null,
              type_id: installationTypeId,
            },
          });
        })(),
        0,
        "Failed to load install ongoing count"
      ),

      safeQuery(
        (async () => {
          if (!repairTypeId) return 0;
          return prisma.monitoringRecord.count({
            where: {
              deleted_at: null,
              done_at: null,
              time_start: null,
              type_id: repairTypeId,
            },
          });
        })(),
        0,
        "Failed to load repair for-dispatch count"
      ),

      safeQuery(
        (async () => {
          if (!repairTypeId) return 0;
          return prisma.monitoringRecord.count({
            where: {
              deleted_at: null,
              time_start: { not: null },
              done_at: null,
              type_id: repairTypeId,
            },
          });
        })(),
        0,
        "Failed to load repair ongoing count"
      ),
    ]);

    const pendingMap = Object.fromEntries(pendingMonitoring.map((p) => [p.tab_type, p._count._all]));

    const monitoringStatusOptions = await safeQuery(
      prisma.configOption.findMany({ where: { list_type: "STATUS", module: "MONITORING" } }),
      [],
      "Failed to load monitoring status options"
    );
    const monitoringStatusLabelById = new Map(monitoringStatusOptions.map((o) => [o.id, o.label]));

    const monitoringBaseStatusCounts = await safeQuery(
      prisma.monitoringRecord.groupBy({
        by: ["status_id", "tab_type"],
        where: {
          deleted_at: null,
          ...range.dateFilter,
          tab_type: { in: ["INTERNET_INSTALL", "CIGNAL_PLAY", "CLIENT_CONCERNS"] },
        },
        _count: { _all: true },
      }),
      [],
      "Failed to load monitoring status counts"
    );

    const monitoringOverallStatus: Record<string, number> = {};
    const monitoringInternetInstall: Record<string, number> = {};
    const monitoringCignalPlay: Record<string, number> = {};
    const monitoringClientConcerns: Record<string, number> = {};

    for (const row of monitoringBaseStatusCounts) {
      const label = monitoringStatusLabelById.get(row.status_id) ?? "Unknown";
      const count = row._count._all;
      monitoringOverallStatus[label] = (monitoringOverallStatus[label] ?? 0) + count;
      if (row.tab_type === "INTERNET_INSTALL") monitoringInternetInstall[label] = (monitoringInternetInstall[label] ?? 0) + count;
      if (row.tab_type === "CIGNAL_PLAY") monitoringCignalPlay[label] = (monitoringCignalPlay[label] ?? 0) + count;
      if (row.tab_type === "CLIENT_CONCERNS") monitoringClientConcerns[label] = (monitoringClientConcerns[label] ?? 0) + count;
    }

    res.json({
      success: true,
      data: {
        as_of: now.toISOString(),
        period: { label: range.label, date_from: range.start?.toISOString() ?? null, date_to: range.end?.toISOString() ?? null },
        stats: {
          total_dispatches: totalDispatches,
          installs,
          repairs,
          concerns,
          ongoing: ongoingDispatches,
          closed: closedCount,
          cancelled: cancelledCount,
        },
pending_monitoring: {
          total: (pendingMap["INTERNET_INSTALL"] ?? 0) + (pendingMap["CIGNAL_PLAY"] ?? 0) + (pendingMap["CLIENT_CONCERNS"] ?? 0),
          internet_install: pendingMap["INTERNET_INSTALL"] ?? 0,
          cignal_play: pendingMap["CIGNAL_PLAY"] ?? 0,
          client_concerns: pendingMap["CLIENT_CONCERNS"] ?? 0,
        },
        install_stats: {
          for_dispatch: installForDispatch,
          ongoing: installOngoing,
        },
        repair_stats: {
          for_dispatch: repairForDispatch,
          ongoing: repairOngoing,
        },
        monitoring_status: {
          overall: monitoringOverallStatus,
          internet_install: monitoringInternetInstall,
          cignal_play: monitoringCignalPlay,
          client_concerns: monitoringClientConcerns,
        },
      },
      warnings,
    });
  } catch (error) {
    sendErrorResponse(res, error, "Unable to load dashboard stats");
  }
}

async function resolveSpanMonths(
  range: ReturnType<typeof resolveDashboardDateRange>,
  now: Date
): Promise<number> {
  let spanStart = range.start;
  if (!spanStart) {
    const earliest = await prisma.dispatch.aggregate({
      _min: { date: true },
      where: { deleted_at: null },
    });
    spanStart = earliest._min.date ?? now;
  }
  const spanEnd = range.end ?? now;
  return monthSpan(spanStart, spanEnd);
}

export async function getByStaff(req: Request, res: Response) {
  try {
    const { date_from, date_to } = DashboardQuerySchema.parse(req.query);
    const range = resolveDashboardDateRange(date_from, date_to);
    const now = new Date();

    const lower = range.start ?? MIN_DATE;
    const upper = range.end ?? MAX_DATE;

    const [installationTypeId, repairTypeId] = await Promise.all([
      getOptionIdOrNull("TYPE", "DISPATCH", "Installation"),
      getOptionIdOrNull("TYPE", "DISPATCH", "Repair"),
    ]);

    const warnings: string[] = [];
    if (!installationTypeId) warnings.push("Installation type option unavailable; installation counts may be incomplete.");
    if (!repairTypeId) warnings.push("Repair type option unavailable; repair counts may be incomplete.");

    const techStats = await safeQuery(
      prisma.$queryRaw<
        {
          technician_id: number;
          name: string;
          installs: bigint;
          repairs: bigint;
          target_per_day: number;
          target_per_month: number;
        }[]
      >`
        SELECT
          t.id AS technician_id,
          t.name,
          t.target_per_day,
          t.target_per_month,
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
      "Failed to load staff dashboard stats"
    );

    const monthCount = await safeQuery(resolveSpanMonths(range, now), 1, "Failed to resolve dashboard month span");
    const workingDays = monthCount * 26;

    const rankedTechs = techStats.map((tech) => {
      const installs = Number(tech.installs);
      const repairs = Number(tech.repairs);
      const total = installs + repairs;
      return { ...tech, total };
    });
    rankedTechs.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));

    const productivityRankMap = new Map<number, number>();
    rankedTechs.forEach((tech, idx) => {
      productivityRankMap.set(tech.technician_id, idx + 1);
    });

    const data = rankedTechs.map((tech) => {
      const installs = Number(tech.installs);
      const repairs = Number(tech.repairs);
      const total = installs + repairs;
      const targetPerMonth = tech.target_per_month ?? 0;
      const scaledTarget = targetPerMonth * monthCount;
      const percentageOfProduct =
        scaledTarget > 0 ? (total / scaledTarget) * 100 : null;
      const perDay = workingDays > 0 ? total / workingDays : 0;

      return {
        technician_id: tech.technician_id,
        technician: tech.name,
        installs,
        repairs,
        total,
        target_per_day: tech.target_per_day ?? 0,
        target_per_month: targetPerMonth,
        percentage_of_product:
          percentageOfProduct !== null
            ? parseFloat(percentageOfProduct.toFixed(2))
            : null,
        per_day: parseFloat(perDay.toFixed(2)),
        productivity_rank: productivityRankMap.get(tech.technician_id) ?? 0,
      };
    });

    res.json({
      success: true,
      data,
      period: { label: range.label, month_count: monthCount },
      warnings,
    });
  } catch (error) {
    sendErrorResponse(res, error, "Unable to load staff dashboard stats");
  }
}

export async function getByTeam(req: Request, res: Response) {
  try {
    const { date_from, date_to } = DashboardQuerySchema.parse(req.query);
    const range = resolveDashboardDateRange(date_from, date_to);
    const now = new Date();

    const lower = range.start ?? MIN_DATE;
    const upper = range.end ?? MAX_DATE;

    const [installationTypeId, repairTypeId] = await Promise.all([
      getOptionIdOrNull("TYPE", "DISPATCH", "Installation"),
      getOptionIdOrNull("TYPE", "DISPATCH", "Repair"),
    ]);

    const warnings: string[] = [];
    if (!installationTypeId) warnings.push("Installation type option unavailable; installation counts may be incomplete.");
    if (!repairTypeId) warnings.push("Repair type option unavailable; repair counts may be incomplete.");

    const teamStats = await safeQuery(
      prisma.$queryRaw<
        {
          team_id: number | null;
          team_name: string;
          member_count: bigint;
          installs: bigint;
          repairs: bigint;
          target_per_day: bigint;
          target_per_month: bigint;
        }[]
      >`
        WITH tech AS (
          SELECT
            t.id,
            t.team_id,
            t.target_per_day,
            t.target_per_month,
            COUNT(CASE WHEN d.type_id = ${installationTypeId} THEN 1 END) AS installs,
            COUNT(CASE WHEN d.type_id = ${repairTypeId} THEN 1 END) AS repairs
          FROM "Technician" t
          LEFT JOIN "DispatchTeam" dt ON dt.technician_id = t.id
          LEFT JOIN "Dispatch" d ON d.id = dt.dispatch_id AND d.deleted_at IS NULL AND d.done_at >= ${lower} AND d.done_at <= ${upper}
          WHERE t.deleted_at IS NULL
          GROUP BY t.id, t.team_id, t.target_per_day, t.target_per_month
        )
        SELECT
          tech.team_id,
          COALESCE(tm.name, 'Unassigned') AS team_name,
          COUNT(*) AS member_count,
          SUM(tech.installs) AS installs,
          SUM(tech.repairs) AS repairs,
          SUM(tech.target_per_day) AS target_per_day,
          SUM(tech.target_per_month) AS target_per_month
        FROM tech
        LEFT JOIN "Team" tm ON tm.id = tech.team_id
        GROUP BY tech.team_id, tm.name
        ORDER BY (SUM(tech.installs) + SUM(tech.repairs)) DESC, team_name ASC
      `,
      [],
      "Failed to load team dashboard stats"
    );

    const monthCount = await safeQuery(resolveSpanMonths(range, now), 1, "Failed to resolve dashboard month span");
    const workingDays = monthCount * 26;

    const data = teamStats.map((team) => {
      const installs = Number(team.installs);
      const repairs = Number(team.repairs);
      const total = installs + repairs;
      const targetPerMonth = Number(team.target_per_month);
      const scaledTarget = targetPerMonth * monthCount;
      const percentageOfProduct = scaledTarget > 0 ? (total / scaledTarget) * 100 : null;
      const perDay = workingDays > 0 ? total / workingDays : 0;

      return {
        team_id: team.team_id,
        team: team.team_name,
        member_count: Number(team.member_count),
        installs,
        repairs,
        total,
        target_per_day: Number(team.target_per_day),
        target_per_month: targetPerMonth,
        percentage_of_product:
          percentageOfProduct !== null
            ? parseFloat(percentageOfProduct.toFixed(2))
            : null,
        per_day: parseFloat(perDay.toFixed(2)),
      };
    });

    res.json({
      success: true,
      data,
      period: { label: range.label, month_count: monthCount },
      warnings,
    });
  } catch (error) {
    sendErrorResponse(res, error, "Unable to load team dashboard stats");
  }
}


export async function getByAdmin(req: Request, res: Response) {
  try {
    const { date_from, date_to } = DashboardQuerySchema.parse(req.query);
    const range = resolveDashboardDateRange(date_from, date_to);

    const lower = range.start ?? MIN_DATE;
    const upper = range.end ?? MAX_DATE;

    const [installationTypeId, repairTypeId, doneStatusId, cancelledStatusId, concernsChatTypeId] = await Promise.all([
      getOptionIdOrNull("TYPE", "DISPATCH", "Installation"),
      getOptionIdOrNull("TYPE", "DISPATCH", "Repair"),
      getOptionIdOrNull("STATUS", "DISPATCH", "Done"),
      getOptionIdOrNull("STATUS", "DISPATCH", "Cancelled"),
      getOptionIdOrNull("CHAT_TYPE", "DISPATCH", "Concern"),
    ]);

    const warnings: string[] = [];
    if (!installationTypeId) warnings.push("Installation type option unavailable; dispatch counts may be incomplete.");
    if (!repairTypeId) warnings.push("Repair type option unavailable; dispatch counts may be incomplete.");
    if (!doneStatusId) warnings.push("Done status option unavailable; close-rate figures may be incomplete.");
    if (!cancelledStatusId) warnings.push("Cancelled status option unavailable; close-rate figures may be inaccurate.");
    if (!concernsChatTypeId) warnings.push("Concern chat type option unavailable; concern counts may be incomplete.");

    const adminStats = await safeQuery(
      prisma.$queryRaw<
        {
          csr_id: number;
          name: string;
          total_records: bigint;
          dispatch_handled: bigint;
          dispatch_closed: bigint;
          dispatch_cancelled: bigint;
          concerns_handled: bigint;
          concerns_closed: bigint;
          concerns_cancelled: bigint;
        }[]
      >`
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
      "Failed to load admin dashboard stats"
    );

    const rankedAdmins = adminStats.map((row) => ({
      ...row,
      total: Number(row.total_records),
    }));
    rankedAdmins.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));

    const adminRankMap = new Map<number, number>();
    rankedAdmins.forEach((row, idx) => {
      adminRankMap.set(row.csr_id, idx + 1);
    });

    const data = rankedAdmins.map((row) => {
      const totalRecords = Number(row.total_records);
      const dispatchHandled = Number(row.dispatch_handled);
      const dispatchClosed = Number(row.dispatch_closed);
      const dispatchCancelled = Number(row.dispatch_cancelled);
      const concernsHandled = Number(row.concerns_handled);
      const concernsClosed = Number(row.concerns_closed);
      const concernsCancelled = Number(row.concerns_cancelled);

      const dispatchEffectiveBase = dispatchHandled - dispatchCancelled;
      const concernsEffectiveBase = concernsHandled - concernsCancelled;

      return {
        csr_id: row.csr_id,
        csr: row.name,
        total_records: totalRecords,
        dispatch_handled: dispatchHandled,
        dispatch_closed: dispatchClosed,
        dispatch_cancelled: dispatchCancelled,
        dispatch_close_rate:
          dispatchEffectiveBase > 0
            ? parseFloat(((dispatchClosed / dispatchEffectiveBase) * 100).toFixed(2))
            : 0,
        concerns_handled: concernsHandled,
        concerns_closed: concernsClosed,
        concerns_cancelled: concernsCancelled,
        concerns_close_rate:
          concernsEffectiveBase > 0
            ? parseFloat(((concernsClosed / concernsEffectiveBase) * 100).toFixed(2))
            : 0,
        rank: adminRankMap.get(row.csr_id) ?? 0,
      };
    });

    res.json({
      success: true,
      data,
      period: { label: range.label },
      warnings,
    });
  } catch (error) {
    sendErrorResponse(res, error, "Unable to load admin dashboard stats");
  }
}

export async function getMonitoringSummary(req: Request, res: Response) {
  try {
    const { date_from, date_to } = DashboardQuerySchema.parse(req.query);
    const range = resolveDashboardDateRange(date_from, date_to);

    const [
      internetPendingId,
      dispatchDoneId, dispatchCancelledId,
    ] = await Promise.all([
      getOptionIdOrNull("STATUS", "MONITORING", "Pending"),
      getOptionIdOrNull("STATUS", "DISPATCH", "Done"),
      getOptionIdOrNull("STATUS", "DISPATCH", "Cancelled"),
    ]);

    const tabTypes = ["INTERNET_INSTALL", "CIGNAL_PLAY", "CLIENT_CONCERNS"] as const;

    const results = await Promise.all(
      tabTypes.map(async (tabType) => {
        const pendingId = internetPendingId;

        const tabWhere = { tab_type: tabType, deleted_at: null as null };

        const [pending, completed, cancelled] = await Promise.all([
          pendingId
            ? safeQuery(
                prisma.monitoringRecord.count({ where: { ...tabWhere, status_id: pendingId } }),
                0,
                `Failed to load pending ${tabType}`
              )
            : 0,
          safeQuery(
            (async () => {
              if (!dispatchDoneId) return 0;
              const doneFilter = range.doneAtFilter.done_at
                ? { done_at: range.doneAtFilter.done_at }
                : { done_at: { not: null } };
              return prisma.monitoringRecord.count({
                where: {
                  ...tabWhere,
                  ...doneFilter,
                  dispatch: {
                    status_id: dispatchDoneId,
                    deleted_at: null,
                  },
                },
              });
            })(),
            0,
            `Failed to load completed ${tabType}`
          ),
          safeQuery(
            (async () => {
              if (!dispatchCancelledId) return 0;
              const doneFilter = range.doneAtFilter.done_at
                ? { done_at: range.doneAtFilter.done_at }
                : { done_at: { not: null } };
              return prisma.monitoringRecord.count({
                where: {
                  ...tabWhere,
                  ...doneFilter,
                  dispatch: {
                    status_id: dispatchCancelledId,
                    deleted_at: null,
                  },
                },
              });
            })(),
            0,
            `Failed to load cancelled ${tabType}`
          ),
        ]);

        const total = completed + cancelled;
        return { tab_type: tabType, total, pending, completed, cancelled };
      })
    );

    const summary: Record<string, { total: number; pending: number; completed: number; cancelled: number }> = {};
    for (const r of results) {
      summary[r.tab_type] = { total: r.total, pending: r.pending, completed: r.completed, cancelled: r.cancelled };
    }

    res.json({ success: true, data: summary, period: { label: range.label } });
  } catch (error) {
    sendErrorResponse(res, error, "Unable to load monitoring summary");
  }
}

export async function getTargets(req: Request, res: Response) {
  try {
    const { date_from, date_to } = DashboardQuerySchema.parse(req.query);
    const range = resolveDashboardDateRange(date_from, date_to);

    const [installationTypeId, doneStatusId] = await Promise.all([
      getOptionIdOrNull("TYPE", "DISPATCH", "Installation"),
      getOptionIdOrNull("STATUS", "DISPATCH", "Done"),
    ]);

    const targets = await safeQuery(
      prisma.monthlyTarget.findMany({
        orderBy: [{ year: "asc" }, { month: "asc" }],
      }),
      [],
      "Failed to load monthly targets"
    );

    const filtered = targets.filter((t) => {
      if (!range.start && !range.end) return true;
      const monthStart = new Date(Date.UTC(t.year, t.month - 1, 1));
      const monthEnd = new Date(Date.UTC(t.year, t.month, 1));
      if (range.start && monthEnd.getTime() <= range.start.getTime()) return false;
      if (range.end && monthStart.getTime() > range.end.getTime()) return false;
      return true;
    });

    const withActuals = await Promise.all(
      filtered.map(async (t) => {
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
          `Failed to calculate actuals for target ${t.year}-${t.month}`
        );
        return {
          id: t.id,
          month: t.month,
          month_label: monthLabel(t.month),
          year: t.year,
          target: t.target,
          actual,
          remaining: Math.max(0, t.target - actual),
          percentage:
            t.target > 0
              ? parseFloat(((actual / t.target) * 100).toFixed(2))
              : 0,
        };
      })
    );

    res.json({
      success: true,
      data: withActuals,
      period: { label: range.label },
    });
  } catch (error) {
    sendErrorResponse(res, error, "Unable to load dashboard targets");
  }
}

// POST /api/dashboard/targets
export async function upsertTarget(req: Request, res: Response) {
  try {
    const { month, year, target } = MonthlyTargetSchema.parse(req.body);

    const existing = await prisma.monthlyTarget.findUnique({
      where: { month_year: { month, year } },
    });

    const result = await prisma.monthlyTarget.upsert({
      where: { month_year: { month, year } },
      create: { month, year, target },
      update: { target },
    });

    await writeAudit(prisma, {
      action: existing ? "UPDATE" : "CREATE",
      entity_type: "MonthlyTarget",
      entity_id: result.id,
      actor_id: req.user!.id,
      summary: `${existing ? "Updated" : "Set"} target for ${monthLabel(month)} ${year}`,
      before: existing ? { target: existing.target } : undefined,
      after: { month, year, target: result.target },
    });

    emitEntityChanged("monthlyTarget:changed", result.id);
    emitAuditChanged();

    res.json({ success: true, data: result });
  } catch (error) {
    sendErrorResponse(res, error, "Unable to save dashboard target");
  }
}

// DELETE /api/dashboard/targets/:id
export async function deleteTarget(req: Request, res: Response) {
  try {
    const id = parseIdParam(req.params.id);

    const existing = await prisma.monthlyTarget.findUnique({ where: { id } });
    if (!existing) {
      throw new NotFoundError("Monthly target");
    }

    await prisma.monthlyTarget.delete({ where: { id } });

    await writeAudit(prisma, {
      action: "DELETE",
      entity_type: "MonthlyTarget",
      entity_id: id,
      actor_id: req.user!.id,
      summary: `Deleted target for ${monthLabel(existing.month)} ${existing.year}`,
      before: { month: existing.month, year: existing.year, target: existing.target },
    });

    emitEntityChanged("monthlyTarget:changed", id);
    emitAuditChanged();

    res.json({ success: true });
  } catch (error) {
    sendErrorResponse(res, error, "Unable to delete dashboard target");
  }
}