import type { Prisma } from "@prisma/client";

export function buildDateRangeFilter(
  date_from?: string,
  date_to?: string
): { date?: { gte?: Date; lte?: Date } } {
  if (!date_from && !date_to) return {};

  const date: { gte?: Date; lte?: Date } = {};

  if (date_from) {
    date.gte = date_from.includes("T")
      ? new Date(date_from)
      : new Date(`${date_from}T00:00:00.000Z`);
  }

  if (date_to) {
    date.lte = date_to.includes("T")
      ? new Date(date_to)
      : new Date(`${date_to}T23:59:59.999Z`);
  }

  return { date };
}

export function buildDoneAtRangeFilter(
  done_from?: string,
  done_to?: string
): { done_at?: { gte?: Date; lte?: Date } } {
  if (!done_from && !done_to) return {};

  const done_at: { gte?: Date; lte?: Date } = {};

  if (done_from) {
    done_at.gte = done_from.includes("T")
      ? new Date(done_from)
      : new Date(`${done_from}T00:00:00.000Z`);
  }

  if (done_to) {
    done_at.lte = done_to.includes("T")
      ? new Date(done_to)
      : new Date(`${done_to}T23:59:59.999Z`);
  }

  return { done_at };
}

export function buildTextContainsFilter(
  value?: string
): { contains: string; mode: "insensitive" } | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  return { contains: trimmed, mode: "insensitive" };
}

export function buildTicketNumberFilter(
  value?: string
): { startsWith: string; mode: "insensitive" } | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  return { startsWith: trimmed, mode: "insensitive" };
}

export function buildTimeStartRangeFilter(
  time_start_from?: string,
  time_start_to?: string
): { time_start?: { gte?: Date; lte?: Date } } {
  if (!time_start_from && !time_start_to) return {};

  const time_start: { gte?: Date; lte?: Date } = {};

  if (time_start_from) {
    time_start.gte = time_start_from.includes("T")
      ? new Date(time_start_from)
      : new Date(`${time_start_from}T00:00:00.000Z`);
  }

  if (time_start_to) {
    time_start.lte = time_start_to.includes("T")
      ? new Date(time_start_to)
      : new Date(`${time_start_to}T23:59:59.999Z`);
  }

  return { time_start };
}

export function buildTeamFilter(
  teamIds?: number[]
): Prisma.DispatchWhereInput | undefined {
  if (!teamIds?.length) return undefined;
  return { teams: { some: { technician_id: { in: teamIds } } } };
}
