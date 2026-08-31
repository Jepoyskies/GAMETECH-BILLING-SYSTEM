import { Response } from "express";
import { BadRequestError } from "./errors";

export const EXPORT_MAX_DAYS = 31;
export const EXPORT_MAX_ROWS = 20000;

export function monthToRange(month: string): { date_from: string; date_to: string } {
  if (!/^\d{4}-\d{2}$/.test(month)) {
    throw new BadRequestError("Invalid month format, expected YYYY-MM");
  }
  const [year, mon] = month.split("-").map(Number);
  const from = new Date(Date.UTC(year, mon - 1, 1));
  const to = new Date(Date.UTC(year, mon, 0));
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    date_from: `${from.getUTCFullYear()}-${pad(from.getUTCMonth() + 1)}-${pad(from.getUTCDate())}`,
    date_to: `${to.getUTCFullYear()}-${pad(to.getUTCMonth() + 1)}-${pad(to.getUTCDate())}`,
  };
}

export function assertExportRangeAllowed(date_from?: string, date_to?: string) {
  if (!date_from || !date_to) {
    throw new BadRequestError("Both date_from and date_to are required for export");
  }
  const from = new Date(date_from.includes("T") ? date_from : `${date_from}T00:00:00.000Z`);
  const to = new Date(date_to.includes("T") ? date_to : `${date_to}T23:59:59.999Z`);
  const days = (to.getTime() - from.getTime()) / 86400000;

  if (days < 0) throw new BadRequestError("date_from must be before date_to");
  if (days > EXPORT_MAX_DAYS) {
    throw new BadRequestError(`Export range cannot exceed ${EXPORT_MAX_DAYS} days`);
  }
}

function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (/[",\n]/.test(str)) return `"${str.replace(/"/g, '""')}"`;
  return str;
}

export function sendCsv(
  res: Response,
  filename: string,
  headers: string[],
  rows: (string | number | null | undefined)[][]
) {
  res.setHeader("Content-Type", "text/csv; charset=utf-8");
  res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);

  res.write(headers.map(csvEscape).join(",") + "\n");
  for (const row of rows) {
    res.write(row.map(csvEscape).join(",") + "\n");
  }
  res.end();
}

export function fmtDateTime(d: Date | null | undefined, timeZone = "Asia/Manila"): string {
  if (!d) return "";
  return d.toLocaleString("en-US", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  });
}

export function fmtDuration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "";
  const days = Math.floor(minutes / 1440);
  const hrs = Math.floor((minutes % 1440) / 60);
  const mins = minutes % 60;
  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hrs > 0) parts.push(`${hrs}h`);
  if (mins > 0 || parts.length === 0) parts.push(`${mins}m`);
  return parts.join(" ");
}