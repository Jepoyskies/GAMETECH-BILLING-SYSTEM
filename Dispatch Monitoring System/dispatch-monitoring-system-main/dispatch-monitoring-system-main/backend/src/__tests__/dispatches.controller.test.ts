import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Request, Response } from "express";
import type { Role } from "@prisma/client";

const mockPrisma = vi.hoisted(() => ({
  dispatch: {
    findMany: vi.fn(),
    findFirst: vi.fn(),
    update: vi.fn(),
    count: vi.fn(),
  },
  dispatchTeam: { deleteMany: vi.fn() },
  jobDetail: { upsert: vi.fn(), findUnique: vi.fn() },
  configOption: { findUnique: vi.fn() },
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
  resolveCustomerLink: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("../lib/configOptions", () => ({
  assertActiveOption: vi.fn().mockResolvedValue(undefined),
}));

import { listDispatches, getDispatch, updateDispatch, deleteDispatch } from "../controllers/dispatches.controller";

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

beforeEach(() => {
  vi.clearAllMocks();
});

describe("listDispatches", () => {
  const sampleDispatch = {
    id: 1,
    date: new Date("2024-06-01"),
    client: "John Doe",
    address: "123 Main St",
    contact_number: "09171234567",
    concern: "Internet issue",
    sales_agent: "Jane",
    statusOption: { id: 1, label: "Done", color: "#22c55e" },
    typeOption: { id: 1, label: "Installation", color: "#3b82f6" },
    chatTypeOption: { id: 1, label: "Inquiry", color: "#a855f7" },
    teams: [],
    csr: { id: 1, name: "Admin" },
    customer: null,
    monitoring: null,
  };

  it("returns first page with cursor when has_next is true", async () => {
    const records = Array(51).fill(null).map((_, i) => ({
      ...sampleDispatch,
      id: i + 1,
    }));
    mockPrisma.dispatch.findMany.mockResolvedValue(records);

    const req = mockReq({ query: { limit: "50" } });
    const res = mockRes();
    await listDispatches(req, res);

    expect(mockPrisma.dispatch.findMany).toHaveBeenCalledWith(
      expect.objectContaining({ take: 51 })
    );
    expect(res.json).toHaveBeenCalledWith({
      success: true,
      data: records.slice(0, 50),
      pagination: {
        next_cursor: 50,
        has_next: true,
        limit: 50,
      },
    });
  });

  it("returns no next page when results fit in limit", async () => {
    const records = Array(30).fill(null).map((_, i) => ({
      ...sampleDispatch,
      id: i + 1,
    }));
    mockPrisma.dispatch.findMany.mockResolvedValue(records);

    const req = mockReq({ query: { limit: "50" } });
    const res = mockRes();
    await listDispatches(req, res);

    expect(res.json).toHaveBeenCalledWith({
      success: true,
      data: records,
      pagination: {
        next_cursor: null,
        has_next: false,
        limit: 50,
      },
    });
  });

  it("accepts cursor parameter", async () => {
    mockPrisma.dispatch.findMany.mockResolvedValue([sampleDispatch]);

    const req = mockReq({ query: { cursor: "50", limit: "50" } });
    const res = mockRes();
    await listDispatches(req, res);

    expect(mockPrisma.dispatch.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        cursor: { id: 50 },
        skip: 1,
        take: 51,
      })
    );
  });

  it("filters by status_id", async () => {
    mockPrisma.dispatch.findMany.mockResolvedValue([]);
    const req = mockReq({ query: { status_id: "3" } });
    const res = mockRes();
    await listDispatches(req, res);

    expect(mockPrisma.dispatch.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ status_id: 3 }),
      })
    );
  });
});

describe("getDispatch", () => {
  const sampleDispatch = {
    id: 1,
    client: "John Doe",
    date: new Date(),
    statusOption: { id: 1, label: "Pending", color: "#f59e0b" },
    teams: [],
    csr: { id: 1, name: "Admin" },
  };

  it("returns a dispatch by id", async () => {
    mockPrisma.dispatch.findFirst.mockResolvedValue(sampleDispatch);

    const req = mockReq({ params: { id: "1" } });
    const res = mockRes();
    await getDispatch(req, res);

    expect(res.json).toHaveBeenCalledWith({
      success: true,
      data: sampleDispatch,
    });
  });

  it("throws 404 when dispatch not found", async () => {
    mockPrisma.dispatch.findFirst.mockResolvedValue(null);

    const req = mockReq({ params: { id: "999" } });
    const res = mockRes();
    await expect(getDispatch(req, res)).rejects.toThrow("Dispatch not found");
  });
});

describe("updateDispatch", () => {
  const existingDispatch = {
    id: 1,
    client: "John Doe",
    address: "123 Main St",
    contact_number: "09171234567",
    concern: "Issue",
    sales_agent: "Jane",
    date: new Date(),
    time_start: null,
    time_accomplish: null,
    remarks: null,
    latitude: null,
    longitude: null,
    source_tab: "INTERNET_INSTALL",
    ticket_number: null,
    actions_taken: null,
    status_id: 1,
    type_id: 1,
    chat_type_id: 1,
    csr_id: 1,
    customer_id: null,
    done_at: null,
    done_duration: null,
    duration: null,
    statusOption: { id: 1, label: "Pending", color: "#f59e0b" },
    typeOption: { id: 1, label: "Installation", color: "#3b82f6" },
    chatTypeOption: { id: 1, label: "Inquiry", color: "#a855f7" },
    teams: [],
    csr: { id: 1, name: "Admin" },
    customer: null,
    monitoring: null,
    deleted_at: null,
    created_at: new Date(),
    updated_at: new Date(),
  };

  it("updates a dispatch and returns it", async () => {
    mockPrisma.dispatch.findFirst.mockResolvedValue(existingDispatch);
    mockPrisma.dispatch.update.mockResolvedValue({
      ...existingDispatch,
      client: "Updated Name",
    });

    const req = mockReq({
      params: { id: "1" },
      body: { client: "Updated Name" },
    });
    const res = mockRes();
    await updateDispatch(req, res);

    expect(mockPrisma.dispatch.update).toHaveBeenCalled();
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ success: true })
    );
  });

  it("throws 404 when dispatch to update not found", async () => {
    mockPrisma.dispatch.findFirst.mockResolvedValue(null);

    const req = mockReq({ params: { id: "999" }, body: {} });
    const res = mockRes();
    await expect(updateDispatch(req, res)).rejects.toThrow("Dispatch not found");
  });
});

describe("deleteDispatch", () => {
  const existingDispatch = {
    id: 1,
    client: "John Doe",
    date: new Date(),
    statusOption: { id: 1, label: "Pending", color: "#f59e0b" },
    teams: [],
    csr: { id: 1, name: "Admin" },
    deleted_at: null,
  };

  it("soft-deletes a dispatch with matching confirm_name", async () => {
    mockPrisma.dispatch.findFirst.mockResolvedValue(existingDispatch);
    mockPrisma.dispatch.update.mockResolvedValue({
      ...existingDispatch,
      deleted_at: new Date(),
    });

    const req = mockReq({
      params: { id: "1" },
      body: { confirm_name: "John Doe" },
    });
    const res = mockRes();
    await deleteDispatch(req, res);

    expect(mockPrisma.dispatch.update).toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ deleted_at: expect.any(Date) }) })
    );
    expect(res.json).toHaveBeenCalledWith({
      success: true,
      message: "Dispatch deleted",
    });
  });

  it("throws when confirm_name does not match", async () => {
    mockPrisma.dispatch.findFirst.mockResolvedValue(existingDispatch);

    const req = mockReq({
      params: { id: "1" },
      body: { confirm_name: "Wrong Name" },
    });
    const res = mockRes();
    await expect(deleteDispatch(req, res)).rejects.toThrow(
      "Client name does not match"
    );
  });

  it("throws 404 when dispatch to delete not found", async () => {
    mockPrisma.dispatch.findFirst.mockResolvedValue(null);

    const req = mockReq({ params: { id: "999" }, body: { confirm_name: "John" } });
    const res = mockRes();
    await expect(deleteDispatch(req, res)).rejects.toThrow("Dispatch not found");
  });
});
