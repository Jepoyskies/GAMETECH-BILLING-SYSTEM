import { describe, it, expect } from "vitest";
import {
  buildDateRangeFilter,
  buildTextContainsFilter,
  buildTicketNumberFilter,
  buildTeamFilter,
} from "../lib/queryFilters";

describe("buildDateRangeFilter", () => {
  it("returns empty object when no dates provided", () => {
    expect(buildDateRangeFilter()).toEqual({});
    expect(buildDateRangeFilter(undefined, undefined)).toEqual({});
  });

  it("builds a gte filter from date_from (date-only string)", () => {
    const result = buildDateRangeFilter("2024-06-01");
    expect(result.date?.gte).toBeInstanceOf(Date);
    expect(result.date?.gte!.toISOString()).toBe("2024-06-01T00:00:00.000Z");
    expect(result.date?.lte).toBeUndefined();
  });

  it("builds an lte filter from date_to (date-only string)", () => {
    const result = buildDateRangeFilter(undefined, "2024-06-30");
    expect(result.date?.lte).toBeInstanceOf(Date);
    expect(result.date?.lte!.toISOString()).toBe("2024-06-30T23:59:59.999Z");
    expect(result.date?.gte).toBeUndefined();
  });

  it("builds both gte and lte when both provided", () => {
    const result = buildDateRangeFilter("2024-06-01", "2024-06-30");
    expect(result.date?.gte).toBeInstanceOf(Date);
    expect(result.date?.lte).toBeInstanceOf(Date);
  });

  it("accepts ISO datetime strings", () => {
    const result = buildDateRangeFilter("2024-06-01T12:00:00.000Z");
    expect(result.date?.gte!.toISOString()).toBe("2024-06-01T12:00:00.000Z");
  });
});

describe("buildTextContainsFilter", () => {
  it("returns undefined for empty input", () => {
    expect(buildTextContainsFilter()).toBeUndefined();
    expect(buildTextContainsFilter("")).toBeUndefined();
    expect(buildTextContainsFilter("   ")).toBeUndefined();
  });

  it("builds a case-insensitive contains filter", () => {
    const result = buildTextContainsFilter("John");
    expect(result).toEqual({ contains: "John", mode: "insensitive" });
  });

  it("trims whitespace", () => {
    const result = buildTextContainsFilter("  John  ");
    expect(result?.contains).toBe("John");
  });
});

describe("buildTicketNumberFilter", () => {
  it("returns undefined for empty input", () => {
    expect(buildTicketNumberFilter()).toBeUndefined();
    expect(buildTicketNumberFilter("")).toBeUndefined();
  });

  it("builds a case-insensitive startsWith filter", () => {
    const result = buildTicketNumberFilter("GPT-");
    expect(result).toEqual({ startsWith: "GPT-", mode: "insensitive" });
  });

  it("trims whitespace", () => {
    const result = buildTicketNumberFilter("  GPT-001  ");
    expect(result?.startsWith).toBe("GPT-001");
  });
});

describe("buildTeamFilter", () => {
  it("returns undefined for empty array", () => {
    expect(buildTeamFilter()).toBeUndefined();
    expect(buildTeamFilter([])).toBeUndefined();
  });

  it("builds a team filter with some-in condition", () => {
    const result = buildTeamFilter([1, 2, 3]);
    expect(result).toEqual({
      teams: { some: { technician_id: { in: [1, 2, 3] } } },
    });
  });
});
