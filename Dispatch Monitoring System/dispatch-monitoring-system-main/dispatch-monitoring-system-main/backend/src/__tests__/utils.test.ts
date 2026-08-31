import { describe, it, expect } from "vitest";
import {
  computeDuration,
  parseIdParam,
  dedupeTeamIds,
  monthSpan,
  monthLabel,
  parseDateParam,
  flattenStatusCounts,
  resolveMonitoringType,
  parseIntParam,
  resolveDashboardDateRange,
  resolveMonthRange,
} from "../lib/utils";

describe("computeDuration", () => {
  it("returns null when either date is missing", () => {
    expect(computeDuration(null, null)).toBeNull();
    expect(computeDuration(new Date(), null)).toBeNull();
    expect(computeDuration(null, new Date())).toBeNull();
    expect(computeDuration(undefined, undefined)).toBeNull();
  });

  it("computes duration in minutes", () => {
    const start = new Date("2024-06-01T10:00:00Z");
    const end = new Date("2024-06-01T12:30:00Z");
    expect(computeDuration(start, end)).toBe(150);
  });

  it("returns null when end is before start", () => {
    const start = new Date("2024-06-01T12:00:00Z");
    const end = new Date("2024-06-01T10:00:00Z");
    expect(computeDuration(start, end)).toBeNull();
  });

  it("rounds to nearest minute", () => {
    const start = new Date("2024-06-01T10:00:00Z");
    const end = new Date("2024-06-01T10:00:30Z");
    expect(computeDuration(start, end)).toBe(1);
  });
});

describe("parseIdParam", () => {
  it("parses valid numeric strings", () => {
    expect(parseIdParam("1")).toBe(1);
    expect(parseIdParam("100")).toBe(100);
  });

  it("throws ValidationError for invalid inputs", () => {
    expect(() => parseIdParam("abc")).toThrow("Invalid ID");
    expect(() => parseIdParam("0")).toThrow("Invalid ID");
    expect(() => parseIdParam("-1")).toThrow("Invalid ID");
    expect(() => parseIdParam("")).toThrow("Invalid ID");
  });
});

describe("parseIntParam", () => {
  it("parses valid inputs", () => {
    expect(parseIntParam("1")).toBe(1);
    expect(parseIntParam(42)).toBe(42);
  });

  it("returns undefined for null/undefined/empty", () => {
    expect(parseIntParam(undefined)).toBeUndefined();
    expect(parseIntParam(null)).toBeUndefined();
    expect(parseIntParam("")).toBeUndefined();
  });

  it("returns undefined for non-numeric strings", () => {
    expect(parseIntParam("abc")).toBeUndefined();
  });
});

describe("dedupeTeamIds", () => {
  it("removes duplicates", () => {
    expect(dedupeTeamIds([1, 2, 2, 3, 1])).toEqual([1, 2, 3]);
  });

  it("filters out non-positive ids", () => {
    expect(dedupeTeamIds([0, -1, 5, 0])).toEqual([5]);
  });

  it("returns empty array for empty input", () => {
    expect(dedupeTeamIds([])).toEqual([]);
  });
});

describe("monthSpan", () => {
  it("calculates month span between dates", () => {
    const start = new Date("2024-01-01T00:00:00.000Z");
    const end = new Date("2024-03-01T00:00:00.000Z");
    expect(monthSpan(start, end)).toBe(3);
  });

  it("returns at least 1 for same month", () => {
    const start = new Date("2024-06-01T00:00:00.000Z");
    const end = new Date("2024-06-15T00:00:00.000Z");
    expect(monthSpan(start, end)).toBe(1);
  });

  it("handles year boundaries", () => {
    const start = new Date("2023-11-01T00:00:00.000Z");
    const end = new Date("2024-02-01T00:00:00.000Z");
    expect(monthSpan(start, end)).toBe(4);
  });
});

describe("monthLabel", () => {
  it("returns full month name", () => {
    expect(monthLabel(1)).toBe("January");
    expect(monthLabel(6)).toBe("June");
    expect(monthLabel(12)).toBe("December");
  });
});

describe("parseDateParam", () => {
  it("parses valid date strings", () => {
    const result = parseDateParam("2024-06-01T00:00:00.000Z");
    expect(result).toBeInstanceOf(Date);
    expect(result!.toISOString()).toBe("2024-06-01T00:00:00.000Z");
  });

  it("returns undefined for invalid values", () => {
    expect(parseDateParam(undefined)).toBeUndefined();
    expect(parseDateParam("not-a-date")).toBeUndefined();
    expect(parseDateParam("")).toBeUndefined();
  });
});

describe("flattenStatusCounts", () => {
  it("converts array to record", () => {
    const rows = [
      { status: "Done", _count: { status: 10 } },
      { status: "Pending", _count: { status: 5 } },
    ];
    expect(flattenStatusCounts(rows)).toEqual({ Done: 10, Pending: 5 });
  });

  it("returns empty object for empty array", () => {
    expect(flattenStatusCounts([])).toEqual({});
  });
});

describe("resolveMonitoringType", () => {
  it("returns the provided type if non-null", () => {
    expect(resolveMonitoringType("INTERNET_INSTALL", "Repair")).toBe("Repair");
  });

  it("returns INSTALLATION for INTERNET_INSTALL tab with no type", () => {
    expect(resolveMonitoringType("INTERNET_INSTALL")).toBe("INSTALLATION");
  });

  it("returns null for other tabs with no type", () => {
    expect(resolveMonitoringType("CIGNAL_PLAY")).toBeNull();
    expect(resolveMonitoringType("CLIENT_CONCERNS")).toBeNull();
  });
});

describe("resolveDashboardDateRange", () => {
  it("returns all-records label when no dates", () => {
    const result = resolveDashboardDateRange();
    expect(result.label).toBe("All Records");
    expect(result.dateFilter).toEqual({});
  });

  it("builds range from both dates", () => {
    const result = resolveDashboardDateRange("2024-06-01", "2024-06-30");
    expect(result.start).toBeInstanceOf(Date);
    expect(result.end).toBeInstanceOf(Date);
    expect(result.label).toContain("Jun");
    expect(result.label).toContain("2024");
  });

  it("throws when start is after end", () => {
    expect(() => resolveDashboardDateRange("2024-07-01", "2024-06-01")).toThrow(
      "date_from must be before or equal to date_to"
    );
  });
});

describe("resolveMonthRange", () => {
  it("uses provided month and year", () => {
    const result = resolveMonthRange(6, 2024);
    expect(result.targetMonth).toBe(6);
    expect(result.targetYear).toBe(2024);
  });

  it("uses current month/year when not provided", () => {
    const now = new Date();
    const result = resolveMonthRange();
    expect(result.targetMonth).toBe(now.getMonth() + 1);
    expect(result.targetYear).toBe(now.getFullYear());
  });
});
