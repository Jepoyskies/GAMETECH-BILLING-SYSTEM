import prisma from "./prisma";
import { Prisma, SourceTab } from "@prisma/client";
import { ValidationError } from "./errors";

export function computeDuration(
  timeStart: Date | null | undefined,
  timeAccomplish: Date | null | undefined
): number | null {
  if (!timeStart || !timeAccomplish) return null;
  const diff = timeAccomplish.getTime() - timeStart.getTime();
  if (diff < 0) return null;
  return Math.round(diff / 60000);
}

export async function generateTicketNumber(tx?: Prisma.TransactionClient): Promise<string> {
  const client = tx ?? prisma;
  const count = await client.monitoringRecord.count({
    where: { tab_type: "CLIENT_CONCERNS" },
  });
  const next = count + 1;
  const padded = String(next).padStart(7, "0");
  return `GPT-${padded}`;
}

export function parseIdParam(value: string): number {
  const parsed = parseInt(value, 10);
  if (isNaN(parsed) || parsed <= 0) {
    throw new ValidationError(`Invalid ID: "${value}" is not a valid positive integer`);
  }
  return parsed;
}

export function parseIntParam(value: unknown): number | undefined {
  if (value === undefined || value === null || value === "") return undefined;
  const parsed = parseInt(String(value), 10);
  return isNaN(parsed) ? undefined : parsed;
}

export function resolveMonthRange(month?: number, year?: number) {
  const now = new Date();
  const targetMonth = month ?? now.getMonth() + 1;
  const targetYear = year ?? now.getFullYear();
  const monthStart = new Date(targetYear, targetMonth - 1, 1);
  const monthEnd = new Date(targetYear, targetMonth, 1);
  return { targetMonth, targetYear, monthStart, monthEnd };
}

export interface DashboardDateRange {
  start?: Date;
  end?: Date;
  dateFilter: { date?: { gte?: Date; lte?: Date } };
  createdAtFilter: { created_at?: { gte?: Date; lte?: Date } };
  doneAtFilter: { done_at?: { gte?: Date; lte?: Date } };
  label: string;
}

const MONTH_LABELS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const SHORT_MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function parseRangeStart(value?: string): Date | undefined {
  if (!value) return undefined;
  const d = value.includes("T")
    ? new Date(value)
    : new Date(`${value}T00:00:00.000Z`);
  return isNaN(d.getTime()) ? undefined : d;
}

function parseRangeEnd(value?: string): Date | undefined {
  if (!value) return undefined;
  const d = value.includes("T")
    ? new Date(value)
    : new Date(`${value}T23:59:59.999Z`);
  return isNaN(d.getTime()) ? undefined : d;
}

function formatRangeDay(d: Date): string {
  return `${SHORT_MONTH_LABELS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
}

function formatDateRangeLabel(start?: Date, end?: Date): string {
  if (!start && !end) return "All Records";
  if (start && end) {
    const sameDay =
      start.getUTCFullYear() === end.getUTCFullYear() &&
      start.getUTCMonth() === end.getUTCMonth() &&
      start.getUTCDate() === end.getUTCDate();
    return sameDay
      ? formatRangeDay(start)
      : `${formatRangeDay(start)} – ${formatRangeDay(end)}`;
  }
  if (start) return `From ${formatRangeDay(start)}`;
  return `Until ${formatRangeDay(end!)}`;
}

export function resolveDashboardDateRange(
  date_from?: string,
  date_to?: string
): DashboardDateRange {
  const start = parseRangeStart(date_from);
  const end = parseRangeEnd(date_to);

  if (start && end && start.getTime() > end.getTime()) {
    throw new ValidationError("date_from must be before or equal to date_to");
  }

  const date: { gte?: Date; lte?: Date } = {};
  if (start) date.gte = start;
  if (end) date.lte = end;

  const active = !!(start || end);

  return {
    start,
    end,
    dateFilter: active ? { date } : {},
    createdAtFilter: active ? { created_at: { ...date } } : {},
    doneAtFilter: active ? { done_at: { ...date } } : {},
    label: formatDateRangeLabel(start, end),
  };
}

export function monthSpan(start: Date, end: Date): number {
  const s = start.getUTCFullYear() * 12 + start.getUTCMonth();
  const e = end.getUTCFullYear() * 12 + end.getUTCMonth();
  return Math.max(1, e - s + 1);
}

export function monthLabel(month: number): string {
  return MONTH_LABELS[month - 1] ?? String(month);
}

export function flattenStatusCounts(
  rows: { status: string; _count: { status: number } }[]
): Record<string, number> {
  return Object.fromEntries(rows.map((s) => [s.status, s._count.status]));
}

export function parseDateParam(value: unknown): Date | undefined {
  if (!value || typeof value !== "string") return undefined;
  const d = new Date(value);
  return isNaN(d.getTime()) ? undefined : d;
}

export function resolveMonitoringType(
  tabType: SourceTab | string,
  type?: string | null
): string | null {
  if (type) return type;
  if (tabType === "INTERNET_INSTALL") return "INSTALLATION";
  return null;
}

export function dedupeTeamIds(teams: number[]): number[] {
  return [...new Set(teams.filter((id) => id > 0))];
}
