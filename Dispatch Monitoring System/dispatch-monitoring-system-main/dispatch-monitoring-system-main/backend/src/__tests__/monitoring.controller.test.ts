import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Request, Response } from "express";
import type { Role } from "@prisma/client";

const mockPrisma = vi.hoisted(() => ({
  monitoringRecord: {
    findMany: vi.fn(),
    findFirst: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    count: vi.fn(),
    groupBy: vi.fn(),
  },
  monitoringTeam: { deleteMany: vi.fn(), createMany: vi.fn(), findMany: vi.fn() },
  dispatch: { findFirst: vi.fn() },
  dispatchTeam: { deleteMany: vi.fn(), createMany: vi.fn() },
  jobDetail: { create: vi.fn(), upsert: vi.fn(), findUnique: vi.fn() },
  configOption: { findUnique: vi.fn(), findFirst: vi.fn() },
  $transaction: vi.fn((cb: (tx: unknown) => unknown) => cb(mockPrisma)),
}));

vi.mock("../lib/prisma", () => ({
  default: mockPrisma,
  prisma: mockPrisma,
}));

vi.mock("../lib/audit", () => ({ writeAudit: vi.fn() }));
vi.mock("../lib/socket", () => ({
  emitEntityChanged: vi.fn(),
  emitAuditChanged: vi.fn(),
}));
vi.mock("../lib/customer", () => ({
  resolveCustomerLink: vi.fn().mockResolvedValue(1),
}));
vi.mock("../lib/configOptions", () => ({
  assertActiveOption: vi.fn().mockResolvedValue(undefined),
  tabTypeToConfigModule: vi.fn().mockReturnValue("DISPATCH"),
  getOptionId: vi.fn().mockResolvedValue(1),
}));
vi.mock("../lib/autoDispatch", () => ({
  autoDispatch: vi.fn().mockResolvedValue({ id: 100, client: "John Doe" }),
}));
vi.mock("../lib/utils", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/utils")>();
  return {
    ...actual,
    generateTicketNumber: vi.fn().mockResolvedValue("GPT-0000123"),
  };
});

import {
  createMonitoringRecord,
  markMonitoringRecordDone,
  cancelMonitoringRecord,
  deleteMonitoringRecord,
} from "../controllers/monitoring.controller";

function mockReq(overrides?: Partial<Request>): Request {
  return {
    params: {},
    query: {},
    body: {},
    user: { id: 1, role: "SUPERADMIN" as Role },
    ...overrides,
  } as Request;
}

function mockRes(): Response {
  const res = {} as Response;
  res.status = vi.fn().mockReturnValue(res);
  res.json = vi.fn().mockReturnValue(res);
  return res;
}

const newRecord = {
  id: 1,
  tab_type: "INTERNET_INSTALL",
  date: new Date("2024-06-01"),
  client: "John Doe",
  address: "123 Main St",
  contact_number: "09171234567",
  concern: "Internet issue",
  sales_agent: "Jane",
  statusOption: { id: 1, label: "Pending", color: "#f59e0b" },
  teams: [],
  csr: { id: 1, name: "Admin" },
  dispatch: null,
  customer: null,
  jobDetail: null,
  done_at: null,
  done_duration: null,
  time_start: null,
  time_accomplish: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("createMonitoringRecord", () => {
  it("creates a monitoring record", async () => {
    mockPrisma.monitoringRecord.create.mockResolvedValue(newRecord);

    const req = mockReq({
      body: {
        tab_type: "INTERNET_INSTALL",
        date: "2024-06-01",
        client: "John Doe",
        address: "123 Main St",
        contact_number: "09171234567",
        csr: 1,
        status_id: 1,
        concern: "Internet issue",
      },
    });
    const res = mockRes();
    await createMonitoringRecord(req, res);

    expect(mockPrisma.monitoringRecord.create).toHaveBeenCalled();
    expect(res.status).toHaveBeenCalledWith(201);
    expect(res.json).toHaveBeenCalledWith({
      success: true,
      data: newRecord,
    });
  });

  it("generates ticket number for CLIENT_CONCERNS", async () => {
    mockPrisma.monitoringRecord.create.mockResolvedValue({
      ...newRecord,
      tab_type: "CLIENT_CONCERNS",
      ticket_number: "GPT-0000123",
    });

    const req = mockReq({
      body: {
        tab_type: "CLIENT_CONCERNS",
        date: "2024-06-01",
        client: "John Doe",
        address: "123 Main St",
        contact_number: "09171234567",
        csr: 1,
        status_id: 1,
      },
    });
    const res = mockRes();
    await createMonitoringRecord(req, res);

    const { generateTicketNumber } = await import("../lib/utils");
    expect(generateTicketNumber).toHaveBeenCalled();
  });
});

describe("markMonitoringRecordDone", () => {
  const pendingRecord = {
    ...newRecord,
    time_start: new Date("2024-06-01T08:00:00Z"),
    status_id: 2,
    type_id: 1,
    chat_type_id: 1,
    csr_id: 1,
    customer_id: null,
    source_tab: "INTERNET_INSTALL" as const,
    remarks: null,
    actions_taken: null,
    ticket_number: null,
    latitude: null,
    longitude: null,
    sales_agent: "Jane",
  };

  it("marks a record as done and auto-dispatches", async () => {
    mockPrisma.monitoringRecord.findFirst.mockResolvedValue(pendingRecord);
    mockPrisma.configOption.findFirst.mockResolvedValue({ id: 3, label: "Done" });
    mockPrisma.monitoringRecord.update.mockResolvedValue({
      ...pendingRecord,
      done_at: new Date(),
      status_id: 3,
    });

    const req = mockReq({
      params: { id: "1" },
      body: {
        jobDetail: {
          nap_port: "NAP-01",
          cable_length: "50m",
        },
      },
    });
    const res = mockRes();
    await markMonitoringRecordDone(req, res);

    expect(mockPrisma.monitoringRecord.update).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: 1 },
        data: expect.objectContaining({
          done_at: expect.any(Date),
          done_duration: expect.any(Number),
        }),
      })
    );
    expect(mockPrisma.jobDetail.create).toHaveBeenCalled();
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ success: true })
    );
  });

  it("rejects already completed records", async () => {
    mockPrisma.monitoringRecord.findFirst.mockResolvedValue({
      ...pendingRecord,
      done_at: new Date(),
    });

    const req = mockReq({ params: { id: "1" }, body: {} });
    const res = mockRes();
    await expect(markMonitoringRecordDone(req, res)).rejects.toThrow(
      "Record is already marked as Done"
    );
  });
});

describe("cancelMonitoringRecord", () => {
  const pendingRecord = {
    ...newRecord,
    time_start: new Date("2024-06-01T08:00:00Z"),
    status_id: 2,
    type_id: 1,
    chat_type_id: 1,
    csr_id: 1,
    customer_id: null,
    source_tab: "INTERNET_INSTALL" as const,
    remarks: null,
    actions_taken: null,
    ticket_number: null,
    latitude: null,
    longitude: null,
    sales_agent: "Jane",
  };

  it("cancels a record and creates cancelled dispatch", async () => {
    mockPrisma.monitoringRecord.findFirst.mockResolvedValue(pendingRecord);
    mockPrisma.monitoringRecord.update.mockResolvedValue({
      ...pendingRecord,
      done_at: new Date(),
    });
    mockPrisma.configOption.findFirst.mockResolvedValue({ id: 4, label: "Done" });

    const req = mockReq({
      params: { id: "1" },
      body: { reason: "Customer not available" },
    });
    const res = mockRes();
    await cancelMonitoringRecord(req, res);

    expect(mockPrisma.monitoringRecord.update).toHaveBeenCalled();
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ success: true })
    );
  });

  it("rejects cancellation of already completed records", async () => {
    mockPrisma.monitoringRecord.findFirst.mockResolvedValue({
      ...pendingRecord,
      done_at: new Date(),
    });

    const req = mockReq({ params: { id: "1" }, body: { reason: "Test" } });
    const res = mockRes();
    await expect(cancelMonitoringRecord(req, res)).rejects.toThrow(
      "Record is already completed"
    );
  });
});

describe("deleteMonitoringRecord", () => {
  const existing = {
    ...newRecord,
    teams: [{ id: 1, technician: { id: 1, name: "Tech A" } }],
    csr: { id: 1, name: "Admin" },
  };

  it("soft-deletes a record with matching confirm_name", async () => {
    mockPrisma.monitoringRecord.findFirst.mockResolvedValue(existing);
    mockPrisma.monitoringRecord.update.mockResolvedValue({
      ...existing,
      deleted_at: new Date(),
    });

    const req = mockReq({
      params: { id: "1" },
      body: { confirm_name: "John Doe" },
    });
    const res = mockRes();
    await deleteMonitoringRecord(req, res);

    expect(res.json).toHaveBeenCalledWith({
      success: true,
      message: "Monitoring record deleted",
    });
  });

  it("rejects deletion of completed records", async () => {
    mockPrisma.monitoringRecord.findFirst.mockResolvedValue({
      ...existing,
      done_at: new Date(),
    });

    const req = mockReq({
      params: { id: "1" },
      body: { confirm_name: "John Doe" },
    });
    const res = mockRes();
    await expect(deleteMonitoringRecord(req, res)).rejects.toThrow(
      "Cannot delete a completed record"
    );
  });
});
