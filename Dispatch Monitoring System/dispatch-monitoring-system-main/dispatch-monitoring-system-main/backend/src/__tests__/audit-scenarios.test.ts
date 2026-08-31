import { describe, it, expect, vi, beforeEach } from "vitest";

const mockCreate = vi.fn();
const mockPrisma = {
  auditLog: { create: mockCreate },
};

vi.mock("../lib/prisma", () => ({
  default: mockPrisma,
  prisma: mockPrisma,
}));

import { writeAudit, hasMeaningfulChange } from "../lib/audit";

function fakeDate(iso: string) {
  return new Date(iso);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SCENARIO: Admin edits CSR name only", () => {

  it("shows ONLY Name changed — no password_hash, email, role, or dates leak", async () => {
    const existing = {
      id: 5,
      name: "Old Name",
      email: "old@email.com",
      role: "CSR_ADMIN",
      password_hash: "$2b$10$abc123...",
      failed_login_attempts: 0,
      locked_until: null,
      last_login_at: fakeDate("2026-07-01T08:00:00.000Z"),
      created_at: fakeDate("2026-01-01T00:00:00.000Z"),
      updated_at: fakeDate("2026-07-18T10:00:00.000Z"),
      deleted_at: null,
    };

    const updated = {
      ...existing,
      name: "New Name",
      updated_at: fakeDate("2026-07-18T10:30:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "CSR",
      entity_id: 5,
      actor_id: 1,
      summary: "Updated CSR New Name",
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const storedBefore = stored.before as Record<string, unknown>;
    const storedAfter = stored.after as Record<string, unknown>;

    expect(storedBefore).not.toHaveProperty("password_hash");
    expect(storedAfter).not.toHaveProperty("password_hash");
    expect(storedBefore).not.toHaveProperty("updated_at");
    expect(storedAfter).not.toHaveProperty("updated_at");
    expect(storedBefore.failed_login_attempts).toBe(0);
    expect(storedAfter.failed_login_attempts).toBe(0);
    expect(storedBefore.locked_until).toBeNull();
    expect(storedAfter.locked_until).toBeNull();
    expect(storedBefore.name).toBe("Old Name");
    expect(storedAfter.name).toBe("New Name");
    expect(storedBefore.email).toBe(storedAfter.email);
    expect(storedBefore.role).toBe(storedAfter.role);
    expect(storedBefore.last_login_at).toBe(storedAfter.last_login_at);
    expect(storedBefore.created_at).toBe(storedAfter.created_at);
    expect(storedBefore.deleted_at).toBe(storedAfter.deleted_at);

    expect(hasMeaningfulChange(existing, updated)).toBe(true);
  });
});

describe("SCENARIO: User edits dispatch status only (Pending → Done)", () => {

  it("shows ONLY Status changed — date, client, done_at, address all stay the same", async () => {
    const existing = {
      id: 42,
      date: fakeDate("2026-07-15T10:00:00.000Z"),
      client: "Juan dela Cruz",
      address: "123 Main St",
      contact_number: "09171234567",
      concern: "No internet connection",
      sales_agent: "Maria",
      statusOption: { id: 1, label: "Pending", color: "#f59e0b" },
      typeOption: { id: 1, label: "Installation", color: "#3b82f6" },
      chatTypeOption: { id: 1, label: "Inquiry", color: "#a855f7" },
      latitude: 14.5,
      longitude: 121.0,
      remarks: null,
      time_start: null,
      time_accomplish: null,
      done_at: null,
      duration: null,
      done_duration: null,
      source_tab: "INTERNET_INSTALL",
      ticket_number: null,
      actions_taken: null,
      teams: [],
      csr: { id: 1, name: "Admin" },
      customer: null,
      deleted_at: null,
      created_at: fakeDate("2026-07-15T10:00:00.000Z"),
      updated_at: fakeDate("2026-07-15T10:00:00.000Z"),
    };

    const updated = {
      ...existing,
      statusOption: { id: 3, label: "Done", color: "#22c55e" },
      updated_at: fakeDate("2026-07-18T14:30:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 42,
      actor_id: 1,
      summary: "Updated dispatch for Juan dela Cruz",
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const before = stored.before as Record<string, unknown>;
    const after = stored.after as Record<string, unknown>;

    expect(before.statusOption).toBe("Pending");
    expect(after.statusOption).toBe("Done");
    expect(before.date).toBe(after.date);
    expect(before.client).toBe(after.client);
    expect(before.address).toBe(after.address);
    expect(before.contact_number).toBe(after.contact_number);
    expect(before.concern).toBe(after.concern);
    expect(before.sales_agent).toBe(after.sales_agent);
    expect(before.typeOption).toBe(after.typeOption);
    expect(before.chatTypeOption).toBe(after.chatTypeOption);
    expect(before.latitude).toBe(after.latitude);
    expect(before.longitude).toBe(after.longitude);
    expect(before.remarks).toBe(after.remarks);
    expect(before.time_start).toBe(after.time_start);
    expect(before.time_accomplish).toBe(after.time_accomplish);
    expect(before.done_at).toBeNull();
    expect(after.done_at).toBeNull();
    expect(before).not.toHaveProperty("updated_at");
    expect(after).not.toHaveProperty("updated_at");
    expect(before).not.toHaveProperty("duration");
    expect(after).not.toHaveProperty("duration");
    expect(before).not.toHaveProperty("done_duration");
    expect(after).not.toHaveProperty("done_duration");

    expect(hasMeaningfulChange(existing, updated)).toBe(true);
  });
});

describe("SCENARIO: User edits dispatch date only", () => {

  it("shows ONLY Date changed — status, client, address all unchanged", async () => {
    const existing = {
      id: 50,
      date: fakeDate("2026-07-15T10:00:00.000Z"),
      client: "Maria Santos",
      address: "456 New Ave",
      concern: "Slow internet",
      statusOption: { id: 1, label: "Pending" },
      typeOption: { id: 1, label: "Installation" },
      teams: [],
      csr: { id: 1, name: "Admin" },
      done_at: null,
      updated_at: fakeDate("2026-07-15T10:00:00.000Z"),
    };

    const updated = {
      ...existing,
      date: fakeDate("2026-07-20T10:00:00.000Z"),
      updated_at: fakeDate("2026-07-18T14:30:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 50,
      actor_id: 1,
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const before = stored.before as Record<string, unknown>;
    const after = stored.after as Record<string, unknown>;

    expect(before.date).toBe("2026-07-15T10:00:00.000Z");
    expect(after.date).toBe("2026-07-20T10:00:00.000Z");
    expect(before.client).toBe(after.client);
    expect(before.address).toBe(after.address);
    expect(before.concern).toBe(after.concern);
    expect(before.statusOption).toBe(after.statusOption);
    expect(before.typeOption).toBe(after.typeOption);
    expect(before.done_at).toBe(after.done_at);
  });
});

describe("SCENARIO: User edits monitoring record status only", () => {

  it("shows ONLY Status changed — no date, client, or other fields leak", async () => {
    const existing = {
      id: 60,
      tab_type: "INTERNET_INSTALL",
      date: fakeDate("2026-07-10T08:00:00.000Z"),
      client: "Pedro Reyes",
      address: "789 Oak St",
      contact_number: "09181234567",
      concern: "Installation",
      statusOption: { id: 1, label: "Pending", color: "#f59e0b" },
      typeOption: { id: 1, label: "Installation" },
      chatTypeOption: null,
      teams: [],
      csr: { id: 1, name: "Admin" },
      time_start: null,
      time_accomplish: null,
      done_at: null,
      remarks: "Call customer first",
      customer: null,
      jobDetail: null,
      dispatch: null,
      deleted_at: null,
      created_at: fakeDate("2026-07-10T08:00:00.000Z"),
      updated_at: fakeDate("2026-07-10T08:00:00.000Z"),
    };

    const updated = {
      ...existing,
      statusOption: { id: 3, label: "Ongoing", color: "#3b82f6" },
      updated_at: fakeDate("2026-07-18T11:00:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: 60,
      actor_id: 1,
      summary: "Updated INTERNET_INSTALL record for Pedro Reyes",
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const before = stored.before as Record<string, unknown>;
    const after = stored.after as Record<string, unknown>;

    expect(before.statusOption).toBe("Pending");
    expect(after.statusOption).toBe("Ongoing");
    expect(before.date).toBe(after.date);
    expect(before.client).toBe(after.client);
    expect(before.address).toBe(after.address);
    expect(before.contact_number).toBe(after.contact_number);
    expect(before.concern).toBe(after.concern);
    expect(before.typeOption).toBe(after.typeOption);
    expect(before.remarks).toBe(after.remarks);
    expect(before.time_start).toBe(after.time_start);
    expect(before.time_accomplish).toBe(after.time_accomplish);
    expect(before.done_at).toBe(after.done_at); // still null — not auto-set
  });
});

describe("SCENARIO: User dispatches a record (sets time_start)", () => {

  it("shows ONLY time_start and status changed — client, date, concern all untouched", async () => {
    const existing = {
      id: 70,
      tab_type: "CIGNAL_PLAY",
      date: fakeDate("2026-07-12T00:00:00.000Z"),
      client: "Ana Cruz",
      address: "321 Pine St",
      contact_number: "09199876543",
      concern: "No signal",
      statusOption: { id: 1, label: "Pending" },
      typeOption: null,
      teams: [],
      csr: { id: 1, name: "Admin" },
      time_start: null,
      time_accomplish: null,
      done_at: null,
      updated_at: fakeDate("2026-07-12T00:00:00.000Z"),
    };

    const updated = {
      ...existing,
      statusOption: { id: 4, label: "Ongoing" },
      time_start: fakeDate("2026-07-18T09:00:00.000Z"),
      updated_at: fakeDate("2026-07-18T09:00:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: 70,
      actor_id: 1,
      summary: "Dispatched CIGNAL_PLAY record for Ana Cruz",
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const before = stored.before as Record<string, unknown>;
    const after = stored.after as Record<string, unknown>;

    expect(before.time_start).toBeNull();
    expect(after.time_start).toBe("2026-07-18T09:00:00.000Z");
    expect(before.statusOption).toBe("Pending");
    expect(after.statusOption).toBe("Ongoing");
    expect(before.date).toBe(after.date);
    expect(before.client).toBe(after.client);
    expect(before.address).toBe(after.address);
    expect(before.contact_number).toBe(after.contact_number);
    expect(before.concern).toBe(after.concern);
    expect(before.time_accomplish).toBe(after.time_accomplish);
    expect(before.done_at).toBe(after.done_at);
  });
});

describe("SCENARIO: User marks monitoring record as Done", () => {

  it("shows status=Done, done_at set — this is INTENTIONAL and CORRECT", async () => {
    const existing = {
      id: 80,
      tab_type: "INTERNET_INSTALL",
      date: fakeDate("2026-07-10T08:00:00.000Z"),
      client: "Juan dela Cruz",
      address: "123 Main St",
      contact_number: "09171234567",
      concern: "Install new connection",
      statusOption: { id: 1, label: "Pending" },
      typeOption: { id: 1, label: "Installation" },
      teams: [{ technician: { id: 1, name: "Pedro" } }],
      time_start: fakeDate("2026-07-10T09:00:00.000Z"),
      time_accomplish: null,
      done_at: null,
      done_duration: null,
      updated_at: fakeDate("2026-07-10T09:00:00.000Z"),
    };

    const doneAt = fakeDate("2026-07-18T14:30:00.000Z");
    const updated = {
      ...existing,
      statusOption: { id: 3, label: "Done" },
      done_at: doneAt,
      done_duration: 12090,
      updated_at: fakeDate("2026-07-18T14:30:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: 80,
      actor_id: 1,
      summary: "Marked INTERNET_INSTALL record for Juan dela Cruz as Done",
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const before = stored.before as Record<string, unknown>;
    const after = stored.after as Record<string, unknown>;

    expect(before.statusOption).toBe("Pending");
    expect(after.statusOption).toBe("Done");
    expect(before.done_at).toBeNull();
    expect(after.done_at).toBe("2026-07-18T14:30:00.000Z");
    expect(before).not.toHaveProperty("done_duration");
    expect(after).not.toHaveProperty("done_duration");
    expect(before.date).toBe(after.date);
    expect(before.client).toBe(after.client);
    expect(before.address).toBe(after.address);
    expect(before.contact_number).toBe(after.contact_number);
    expect(before.concern).toBe(after.concern);
    expect(before.time_start).toBe(after.time_start);
    expect(before.time_accomplish).toBe(after.time_accomplish);
  });
});

describe("SCENARIO: User cancels a monitoring record", () => {

  it("shows status=Cancelled, done_at set — intentional changes only", async () => {
    const existing = {
      id: 90,
      tab_type: "CLIENT_CONCERNS",
      date: fakeDate("2026-07-14T00:00:00.000Z"),
      client: "Maria Santos",
      address: "456 New Ave",
      concern: "Billing issue",
      statusOption: { id: 1, label: "Pending" },
      teams: [],
      time_start: null,
      done_at: null,
      done_duration: null,
      updated_at: fakeDate("2026-07-14T00:00:00.000Z"),
    };

    const cancelledAt = fakeDate("2026-07-18T15:00:00.000Z");
    const updated = {
      ...existing,
      statusOption: { id: 5, label: "Cancelled" },
      done_at: cancelledAt,
      done_duration: 6540,
      updated_at: fakeDate("2026-07-18T15:00:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: 90,
      actor_id: 1,
      summary: "Cancelled CLIENT_CONCERNS record for Maria Santos",
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const before = stored.before as Record<string, unknown>;
    const after = stored.after as Record<string, unknown>;

    expect(before.statusOption).toBe("Pending");
    expect(after.statusOption).toBe("Cancelled");
    expect(before.done_at).toBeNull();
    expect(after.done_at).toBe("2026-07-18T15:00:00.000Z");
    expect(before).not.toHaveProperty("done_duration");
    expect(before.date).toBe(after.date);
    expect(before.client).toBe(after.client);
    expect(before.concern).toBe(after.concern);
    expect(before.time_start).toBe(after.time_start);
  });
});

describe("SCENARIO: User edits customer address only", () => {

  it("shows ONLY Address changed — name, contact, coordinates all unchanged", async () => {
    const existing = {
      id: 30,
      name: "Carlos Reyes",
      address: "Old Street 123",
      contact_number: "09175551234",
      email: "carlos@email.com",
      barangay_city: "Barangay Old",
      latitude: 14.5,
      longitude: 121.0,
      deleted_at: null,
      created_at: fakeDate("2026-01-01T00:00:00.000Z"),
      updated_at: fakeDate("2026-06-01T00:00:00.000Z"),
    };

    const updated = {
      ...existing,
      address: "New Street 456",
      updated_at: fakeDate("2026-07-18T12:00:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Customer",
      entity_id: 30,
      actor_id: 1,
      summary: "Updated customer Carlos Reyes",
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const before = stored.before as Record<string, unknown>;
    const after = stored.after as Record<string, unknown>;

    expect(before.address).toBe("Old Street 123");
    expect(after.address).toBe("New Street 456");
    expect(before.name).toBe(after.name);
    expect(before.contact_number).toBe(after.contact_number);
    expect(before.email).toBe(after.email);
    expect(before.barangay_city).toBe(after.barangay_city);
    expect(before.latitude).toBe(after.latitude);
    expect(before.longitude).toBe(after.longitude);
    expect(before.deleted_at).toBe(after.deleted_at);

    expect(before).not.toHaveProperty("updated_at");
    expect(after).not.toHaveProperty("updated_at");
  });
});

describe("SCENARIO: User clicks Save without changing anything", () => {

  it("does NOT create an audit entry — no meaningless log", async () => {

    const record = {
      id: 99,
      client: "Juan",
      address: "123 St",
      contact_number: "09171234567",
      statusOption: { id: 1, label: "Pending" },
      typeOption: { id: 1, label: "Installation" },
      date: fakeDate("2026-07-15T00:00:00.000Z"),
      teams: [],
      csr: { id: 1, name: "Admin" },
      done_at: null,
      updated_at: fakeDate("2026-07-15T10:00:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 99,
      actor_id: 1,
      before: record,
      after: JSON.parse(JSON.stringify(record)),
    });

    expect(mockCreate).not.toHaveBeenCalled();
  });
});

describe("SCENARIO: User edits both status AND date in one form", () => {

  it("shows BOTH fields changed — only the fields the user touched", async () => {
    const existing = {
      id: 110,
      date: fakeDate("2026-07-15T00:00:00.000Z"),
      client: "Test Client",
      address: "123 St",
      concern: "Issue",
      statusOption: { id: 1, label: "Pending" },
      typeOption: { id: 1, label: "Installation" },
      teams: [],
      csr: { id: 1, name: "Admin" },
      done_at: null,
      updated_at: fakeDate("2026-07-15T00:00:00.000Z"),
    };

    const updated = {
      ...existing,
      date: fakeDate("2026-07-20T00:00:00.000Z"),
      statusOption: { id: 3, label: "Done" },
      done_at: null,
      updated_at: fakeDate("2026-07-18T14:00:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 110,
      actor_id: 1,
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const before = stored.before as Record<string, unknown>;
    const after = stored.after as Record<string, unknown>;

    expect(before.date).toBe("2026-07-15T00:00:00.000Z");
    expect(after.date).toBe("2026-07-20T00:00:00.000Z");
    expect(before.statusOption).toBe("Pending");
    expect(after.statusOption).toBe("Done");
    expect(before.done_at).toBeNull();
    expect(after.done_at).toBeNull();
    expect(before.client).toBe(after.client);
    expect(before.address).toBe(after.address);
    expect(before.concern).toBe(after.concern);
    expect(before.typeOption).toBe(after.typeOption);
  });
});

describe("SCENARIO: User changes assigned technicians only", () => {

  it("shows ONLY teams changed — everything else stays same", async () => {
    const existing = {
      id: 120,
      client: "Team Test",
      address: "Tech St",
      date: fakeDate("2026-07-15T00:00:00.000Z"),
      statusOption: { id: 1, label: "Pending" },
      typeOption: { id: 1, label: "Installation" },
      teams: [
        { technician: { id: 1, name: "Juan", team_id: 1 } },
      ],
      csr: { id: 1, name: "Admin" },
      done_at: null,
      updated_at: fakeDate("2026-07-15T00:00:00.000Z"),
    };

    const updated = {
      ...existing,
      teams: [
        { technician: { id: 1, name: "Juan", team_id: 1 } },
        { technician: { id: 2, name: "Pedro", team_id: 1 } },
      ],
      updated_at: fakeDate("2026-07-18T16:00:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 120,
      actor_id: 1,
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const before = stored.before as Record<string, unknown>;
    const after = stored.after as Record<string, unknown>;

    expect(before.teams).toEqual(["Juan"]);
    expect(after.teams).toEqual(["Juan", "Pedro"]);
    expect(before.date).toBe(after.date);
    expect(before.client).toBe(after.client);
    expect(before.address).toBe(after.address);
    expect(before.statusOption).toBe(after.statusOption);
    expect(before.typeOption).toBe(after.typeOption);
    expect(before.done_at).toBe(after.done_at);
  });
});

describe("SCENARIO: User edits concern/remarks text only", () => {

  it("shows ONLY the text field changed — no date/status side-effects", async () => {
    const existing = {
      id: 130,
      client: "Text Edit Test",
      address: "789 Elm St",
      date: fakeDate("2026-07-16T00:00:00.000Z"),
      concern: "Old concern description",
      remarks: "Old remarks",
      statusOption: { id: 1, label: "Pending" },
      typeOption: { id: 1, label: "Repair" },
      teams: [],
      csr: { id: 1, name: "Admin" },
      done_at: null,
      updated_at: fakeDate("2026-07-16T00:00:00.000Z"),
    };

    const updated = {
      ...existing,
      concern: "Updated concern description",
      updated_at: fakeDate("2026-07-18T17:00:00.000Z"),
    };

    await writeAudit(mockPrisma, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: 130,
      actor_id: 1,
      before: existing,
      after: updated,
    });

    const stored = mockCreate.mock.calls[0][0].data;
    const before = stored.before as Record<string, unknown>;
    const after = stored.after as Record<string, unknown>;

    expect(before.concern).toBe("Old concern description");
    expect(after.concern).toBe("Updated concern description");
    expect(before.remarks).toBe(after.remarks);
    expect(before.client).toBe(after.client);
    expect(before.address).toBe(after.address);
    expect(before.date).toBe(after.date);
    expect(before.statusOption).toBe(after.statusOption);
    expect(before.typeOption).toBe(after.typeOption);
    expect(before.done_at).toBe(after.done_at);
  });
});
