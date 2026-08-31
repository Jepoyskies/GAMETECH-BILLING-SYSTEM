import { describe, it, expect, vi, beforeEach } from "vitest";

const mockCreate = vi.fn();
const mockPrisma = {
  auditLog: { create: mockCreate },
};

vi.mock("../lib/prisma", () => ({
  default: mockPrisma,
}));

import { Prisma } from "@prisma/client";
import {
  writeAudit,
  hasMeaningfulChange,
} from "../lib/audit";

function fakeDate(iso: string) {
  return new Date(iso);
}

function freeze(input: unknown) {
  return JSON.parse(JSON.stringify(input));
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("writeAudit — sanitization (stored before/after)", () => {

  it("strips password_hash, password, and token from stored data", async () => {
    const before = { name: "John", password_hash: "abc", password: "secret", token: "xyz" };
    const after = { name: "John", password_hash: "def", password: "newsecret", token: "xyz2" };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "CSR",
      entity_id: 1,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before).not.toHaveProperty("password_hash");
    expect(stored.before).not.toHaveProperty("password");
    expect(stored.before).not.toHaveProperty("token");
    expect(stored.after).not.toHaveProperty("password_hash");
    expect(stored.after).not.toHaveProperty("password");
    expect(stored.after).not.toHaveProperty("token");
    expect(stored.before.name).toBe("John");
  });

  it("replaces config option relation objects with their label", async () => {
    const before = {
      client: "Maria",
      statusOption: { id: 1, label: "Pending", color: "#f59e0b" },
    };
    const after = {
      client: "Maria",
      statusOption: { id: 2, label: "Done", color: "#22c55e" },
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 10,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before.statusOption).toBe("Pending");
    expect(stored.after.statusOption).toBe("Done");
    expect(stored.before).not.toHaveProperty("id");
  });

  it("replaces csr relation objects with their name", async () => {
    const before = { csr: { id: 1, name: "Admin User" } };
    const after = { csr: { id: 2, name: "New Admin" } };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 5,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before.csr).toBe("Admin User");
    expect(stored.after.csr).toBe("New Admin");
  });

  it("strips config option ID fields (status_id, type_id, etc.)", async () => {
    const before = { client: "Juan", status_id: 1, type_id: 2, chat_type_id: 3, csr_id: 5 };
    const after = { client: "Juan", status_id: 4, type_id: 5, chat_type_id: 6, csr_id: 5 };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 7,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before).not.toHaveProperty("status_id");
    expect(stored.before).not.toHaveProperty("type_id");
    expect(stored.before).not.toHaveProperty("chat_type_id");
    expect(stored.before).not.toHaveProperty("csr_id");
    expect(stored.before.client).toBe("Juan");
  });

  it("strips join-table surrogate keys (id, dispatch_id, technician_id, record_id)", async () => {
    const before = {
      id: 99,
      dispatch_id: 10,
      technician_id: 5,
      record_id: 20,
    };
    const after = {
      id: 99,
      dispatch_id: 10,
      technician_id: 7,
      record_id: 20,
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 10,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before).not.toHaveProperty("id");
    expect(stored.before).not.toHaveProperty("dispatch_id");
    expect(stored.before).not.toHaveProperty("technician_id");
    expect(stored.before).not.toHaveProperty("record_id");
    expect(Object.keys(stored.before)).toHaveLength(0);
  });

  it("strips technician noise fields (contact_number, targets, team_id)", async () => {
    const before = {
      name: "Pedro",
      contact_number: "09171234567",
      target_per_day: 3,
      target_per_month: 60,
      team_id: 2,
    };
    const after = {
      name: "Pedro",
      contact_number: "09189876543",
      target_per_day: 4,
      target_per_month: 80,
      team_id: 3,
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Technician",
      entity_id: 5,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before.name).toBe("Pedro");
    expect(stored.before).not.toHaveProperty("contact_number");
    expect(stored.before).not.toHaveProperty("target_per_day");
    expect(stored.before).not.toHaveProperty("target_per_month");
    expect(stored.before).not.toHaveProperty("team_id");
    expect(stored.after.name).toBe("Pedro");
  });

  it("extracts only name from technician-shaped objects, stripping id and team_id", async () => {
    const before = {
      technician: { id: 5, name: "Pedro", team_id: 2 },
    };
    const after = {
      technician: { id: 5, name: "Pedro Updated", team_id: 3 },
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 10,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before.technician).toEqual({ name: "Pedro" });
    expect(stored.after.technician).toEqual({ name: "Pedro Updated" });
    expect(stored.before.technician).not.toHaveProperty("id");
    expect(stored.before.technician).not.toHaveProperty("team_id");
  });

  it("flattens nested technician array to array of names", async () => {
    const before = {
      teams: [
        { technician: { id: 1, name: "Juan", team_id: 1 } },
        { technician: { id: 2, name: "Pedro", team_id: 1 } },
      ],
    };
    const after = {
      teams: [
        { technician: { id: 3, name: "Maria", team_id: 2 } },
      ],
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: 15,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before.teams).toEqual(["Juan", "Pedro"]);
    expect(stored.after.teams).toEqual(["Maria"]);
  });

  it("converts Date objects to ISO strings", async () => {
    const before = { date: fakeDate("2026-07-01T00:00:00.000Z") };
    const after = { date: fakeDate("2026-07-15T00:00:00.000Z") };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 20,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before.date).toBe("2026-07-01T00:00:00.000Z");
    expect(stored.after.date).toBe("2026-07-15T00:00:00.000Z");
  });

  it("strips updated_at, duration, and done_duration from stored data", async () => {
    const before = {
      client: "Maria",
      updated_at: fakeDate("2026-07-10T00:00:00.000Z"),
      duration: 30,
      done_duration: 15,
    };
    const after = {
      client: "Maria Updated",
      updated_at: fakeDate("2026-07-11T00:00:00.000Z"),
      duration: 35,
      done_duration: 20,
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 25,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before).not.toHaveProperty("updated_at");
    expect(stored.before).not.toHaveProperty("duration");
    expect(stored.before).not.toHaveProperty("done_duration");
    expect(stored.after).not.toHaveProperty("updated_at");
    expect(stored.after.client).toBe("Maria Updated");
  });

  it("handles null/undefined values as Prisma.JsonNull", async () => {
    await writeAudit(mockPrisma, {
      action: "CREATE",
      entity_type: "Customer",
      entity_id: 1,
      actor_id: 1,
      before: undefined,
      after: { name: "New Customer" },
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before).toBe(Prisma.JsonNull);
  });

  it("stores bigint as string via sanitize", async () => {
    mockCreate.mockResolvedValue({ id: 1 });

    await writeAudit(mockPrisma, {
      action: "CREATE",
      entity_type: "Dispatch",
      entity_id: 30,
      actor_id: 1,
      after: { count: BigInt(100) },
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.after.count).toBe("100");
  });
});

describe("hasMeaningfulChange", () => {

  it("returns false when nothing changed", () => {
    const obj = { client: "Juan", address: "123 St", statusOption: { label: "Pending" } };
    expect(hasMeaningfulChange(obj, freeze(obj))).toBe(false);
  });

  it("returns true when a field changed", () => {
    const before = { client: "Juan", status: "Pending" };
    const after = { client: "Juan", status: "Done" };
    expect(hasMeaningfulChange(before, after)).toBe(true);
  });

  it("returns false when only updated_at changed (noise)", () => {
    const before = { client: "Juan", updated_at: fakeDate("2026-07-01T00:00:00.000Z") };
    const after = { client: "Juan", updated_at: fakeDate("2026-07-02T00:00:00.000Z") };
    expect(hasMeaningfulChange(before, after)).toBe(false);
  });

  it("returns false when only duration changed (noise)", () => {
    const before = { client: "Juan", duration: 10 };
    const after = { client: "Juan", duration: 20 };
    expect(hasMeaningfulChange(before, after)).toBe(false);
  });

  it("returns false when second-level difference is only updated_at", () => {
    const before = { client: "Juan", jobDetail: { schedule_date: "2026-07-01", updated_at: "2026-07-01T00:00:00.000Z" } };
    const after = { client: "Juan", jobDetail: { schedule_date: "2026-07-01", updated_at: "2026-07-02T00:00:00.000Z" } };
    expect(hasMeaningfulChange(before, after)).toBe(false);
  });

  it("returns true when nested field changed", () => {
    const before = { client: "Juan", jobDetail: { schedule_date: "2026-07-01", nap_port: "A1" } };
    const after = { client: "Juan", jobDetail: { schedule_date: "2026-07-15", nap_port: "A1" } };
    expect(hasMeaningfulChange(before, after)).toBe(true);
  });

  it("returns false for empty string vs null", () => {
    expect(hasMeaningfulChange({ remarks: "" }, { remarks: null })).toBe(false);
    expect(hasMeaningfulChange({ remarks: null }, { remarks: "" })).toBe(false);
    expect(hasMeaningfulChange({ remarks: "" }, { remarks: undefined })).toBe(false);
  });

  it("returns true when a field goes from null to a value", () => {
    expect(hasMeaningfulChange({ remarks: null }, { remarks: "Done" })).toBe(true);
  });

  it("normalizes dates — seconds difference is ignored for Date objects", () => {
    const before = { done_at: fakeDate("2026-07-15T10:30:15.000Z") };
    const after = { done_at: fakeDate("2026-07-15T10:30:45.000Z") };
    expect(hasMeaningfulChange(before, after)).toBe(false);
  });

  it("does NOT ignore seconds difference for ISO string dates (not Date objects)", () => {
    const before = { done_at: "2026-07-15T10:30:15.000Z" };
    const after = { done_at: "2026-07-15T10:30:45.000Z" };
    expect(hasMeaningfulChange(before, after)).toBe(true);
  });

  it("detects date change when minutes differ", () => {
    const before = { done_at: "2026-07-15T10:30:00.000Z" };
    const after = { done_at: "2026-07-15T11:00:00.000Z" };
    expect(hasMeaningfulChange(before, after)).toBe(true);
  });
});

describe("writeAudit — skip logic (no meaningless audit entries)", () => {

  it("does NOT write audit when before and after are identical", async () => {
    const data = { client: "Juan", address: "123 St" };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 1,
      actor_id: 1,
      before: data,
      after: freeze(data),
    });

    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("does NOT write audit when only updated_at differs", async () => {
    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 1,
      actor_id: 1,
      before: { client: "Juan", updated_at: fakeDate("2026-07-01T00:00:00.000Z") },
      after: { client: "Juan", updated_at: fakeDate("2026-07-02T00:00:00.000Z") },
    });

    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("does NOT write audit when only duration/done_duration differs", async () => {
    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 1,
      actor_id: 1,
      before: { client: "Juan", duration: 10, done_duration: 5 },
      after: { client: "Juan", duration: 20, done_duration: 10 },
    });

    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("ALWAYS writes audit for CREATE actions (even without before/after)", async () => {
    mockCreate.mockResolvedValue({ id: 1 });

    await writeAudit(mockPrisma, {
      action: "CREATE",
      entity_type: "Customer",
      entity_id: 1,
      actor_id: 1,
      summary: "Created customer Juan",
    });

    expect(mockCreate).toHaveBeenCalledTimes(1);
  });

  it("ALWAYS writes audit for DELETE actions", async () => {
    mockCreate.mockResolvedValue({ id: 1 });

    await writeAudit(mockPrisma, {
      action: "DELETE",
      entity_type: "Customer",
      entity_id: 1,
      actor_id: 1,
      summary: "Deleted customer Juan",
      before: { name: "Juan" },
    });

    expect(mockCreate).toHaveBeenCalledTimes(1);
  });
});

describe("SCENARIO: editing only status should not show date as changed", () => {

  it("changes only status — date, client, address stay the same", async () => {
    const before = {
      client: "Juan dela Cruz",
      address: "123 Main St",
      date: "2026-07-15T00:00:00.000Z",
      contact_number: "09171234567",
      concern: "No internet",
      statusOption: { id: 1, label: "Pending", color: "#f59e0b" },
      typeOption: { id: 1, label: "Installation", color: "#3b82f6" },
    };
    const after = {
      client: "Juan dela Cruz",
      address: "123 Main St",
      date: "2026-07-15T00:00:00.000Z",
      contact_number: "09171234567",
      concern: "No internet",
      statusOption: { id: 2, label: "Done", color: "#22c55e" },
      typeOption: { id: 1, label: "Installation", color: "#3b82f6" },
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 42,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;

    expect(stored.before.statusOption).toBe("Pending");
    expect(stored.after.statusOption).toBe("Done");
    expect(stored.before.date).toBe(stored.after.date);
    expect(stored.before.client).toBe("Juan dela Cruz");
    expect(stored.after.client).toBe("Juan dela Cruz");
    expect(stored.before.address).toBe(stored.after.address);
    expect(stored.before.contact_number).toBe(stored.after.contact_number);
    expect(stored.before.concern).toBe(stored.after.concern);
  });
});

describe("SCENARIO: editing only technician assignment should not affect other fields", () => {

  it("changes only assigned technicians — everything else stays same", async () => {
    const before = {
      client: "Maria Santos",
      address: "456 New Ave",
      date: "2026-07-14T00:00:00.000Z",
      typeOption: { id: 1, label: "Installation" },
      teams: [
        { technician: { id: 1, name: "Pedro", team_id: 1 } },
      ],
    };
    const after = {
      client: "Maria Santos",
      address: "456 New Ave",
      date: "2026-07-14T00:00:00.000Z",
      typeOption: { id: 1, label: "Installation" },
      teams: [
        { technician: { id: 1, name: "Pedro", team_id: 1 } },
        { technician: { id: 2, name: "Luis", team_id: 1 } },
      ],
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: 50,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;

    expect(stored.before.date).toBe(stored.after.date);
    expect(stored.before.teams).toEqual(["Pedro"]);
    expect(stored.after.teams).toEqual(["Pedro", "Luis"]);
    expect(stored.before.client).toBe("Maria Santos");
    expect(stored.after.client).toBe("Maria Santos");
  });
});

describe("SCENARIO: editing monitoring schedule date should not affect other job details", () => {

  it("changes only schedule_date — other jobDetail fields stay same", async () => {
    const before = {
      client: "Ana",
      jobDetail: {
        schedule_date: "2026-07-20",
        schedule_time: "10:00 AM",
        nap_port: "B2",
        plan_package: "Fiber 50",
        ont_modem_sn: "SN12345",
      },
    };
    const after = {
      client: "Ana",
      jobDetail: {
        schedule_date: "2026-07-25",
        schedule_time: "10:00 AM",
        nap_port: "B2",
        plan_package: "Fiber 50",
        ont_modem_sn: "SN12345",
      },
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: 55,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;

    expect(stored.before.client).toBe(stored.after.client);
    expect(stored.before.jobDetail.schedule_date).toBe("2026-07-20");
    expect(stored.after.jobDetail.schedule_date).toBe("2026-07-25");
    expect(stored.before.jobDetail.schedule_time).toBe(stored.after.jobDetail.schedule_time);
    expect(stored.before.jobDetail.nap_port).toBe(stored.after.jobDetail.nap_port);
    expect(stored.before.jobDetail.plan_package).toBe(stored.after.jobDetail.plan_package);
    expect(stored.before.jobDetail.ont_modem_sn).toBe(stored.after.jobDetail.ont_modem_sn);
  });
});

describe("SCENARIO: no audit written when form saved without changes", () => {

  it("does not write audit when user clicks save without modifying anything", async () => {
    const data = {
      client: "Juan",
      address: "123 St",
      contact_number: "09171234567",
      statusOption: { id: 1, label: "Pending" },
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 100,
      actor_id: 1,
      before: data,
      after: freeze(data),
    });

    expect(mockCreate).not.toHaveBeenCalled();
  });
});

describe("writeAudit — error handling (never throws)", () => {

  it("does not throw when prisma.create fails", async () => {
    mockCreate.mockRejectedValue(new Error("DB connection lost"));

    await expect(
      writeAudit(mockPrisma, {
        action: "CREATE",
        entity_type: "Customer",
        entity_id: 1,
        actor_id: 1,
        summary: "Created customer test",
      })
    ).resolves.toBeUndefined();
  });

  it("does not throw when passed unexpected data types", async () => {
    mockCreate.mockResolvedValue({ id: 1 });

    await expect(
      writeAudit(mockPrisma, {
        action: "UPDATE",
        entity_type: "Dispatch",
        entity_id: 1,
        actor_id: 1,
        before: { circular: {} as unknown },
        after: { value: 42 },
      })
    ).resolves.toBeUndefined();
  });
});

describe("writeAudit — stored field correctness", () => {

  it("stores all required metadata fields correctly", async () => {
    mockCreate.mockResolvedValue({ id: 1 });

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 42,
      actor_id: 3,
      summary: "Updated dispatch for Juan",
      before: { client: "Juan" },
      after: { client: "Juan Updated" },
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.action).toBe("UPDATE");
    expect(stored.entity_type).toBe("Dispatch");
    expect(stored.entity_id).toBe(42);
    expect(stored.actor_id).toBe(3);
    expect(stored.summary).toBe("Updated dispatch for Juan");
  });

  it("stores null summary as null", async () => {
    mockCreate.mockResolvedValue({ id: 1 });

    await writeAudit(mockPrisma, {
      action: "CREATE",
      entity_type: "Customer",
      entity_id: 1,
      actor_id: 1,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.summary).toBeNull();
  });
});

describe("writeAudit — all entity types", () => {

  const ENTITY_TYPES = [
    "CSR",
    "MonitoringRecord",
    "Dispatch",
    "Customer",
    "Technician",
    "Team",
    "ConfigOption",
    "MonthlyTarget",
  ] as const;

  for (const entityType of ENTITY_TYPES) {
    it(`writes audit for entity type ${entityType}`, async () => {
      mockCreate.mockResolvedValue({ id: 1 });

      await writeAudit(mockPrisma, {
        action: "CREATE",
        entity_type: entityType,
        entity_id: 1,
        actor_id: 1,
        summary: `Created ${entityType}`,
        after: { name: "Test" },
      });

      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({
            entity_type: entityType,
            action: "CREATE",
          }),
        })
      );
    });
  }
});

describe("writeAudit — technician edge cases", () => {

  it("stores null for technician without a name in nested technician array", async () => {
    const before = { teams: [{ technician: { id: 1, team_id: 1 } }] };
    const after = { teams: [] };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: 60,
      actor_id: 1,
      before,
      after,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before.teams).toEqual([null]);
  });

  it("strips technician-shaped nested object to only name", async () => {
    mockCreate.mockResolvedValue({ id: 1 });

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 10,
      actor_id: 1,
      before: { technician: { id: 5, name: "Pedro", team_id: 2 } },
      after: { technician: { id: 5, name: "Pedro Updated", team_id: 2 } },
    });

    const stored = mockCreate.mock.calls[0][0].data;
    expect(stored.before.technician).toEqual({ name: "Pedro" });
    expect(stored.after.technician).toEqual({ name: "Pedro Updated" });
  });
});
