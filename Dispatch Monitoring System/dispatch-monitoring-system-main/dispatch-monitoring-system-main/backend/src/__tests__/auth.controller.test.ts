import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Request, Response } from "express";
import type { Role } from "@prisma/client";

const mockPrisma = vi.hoisted(() => ({
  cSR: {
    count: vi.fn(),
    create: vi.fn(),
    findFirst: vi.fn(),
    findMany: vi.fn(),
    update: vi.fn(),
  },
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

const mockHashPassword = vi.hoisted(() => vi.fn().mockResolvedValue("$2a$10$hashedpassword"));
const mockVerifyPassword = vi.hoisted(() => vi.fn());
const mockSignToken = vi.hoisted(() => vi.fn().mockReturnValue("jwt-token"));

vi.mock("../lib/auth", () => ({
  AUTH_COOKIE: "session",
  MAX_FAILED_ATTEMPTS: 5,
  LOCKOUT_MINUTES: 15,
  authCookieOptions: vi.fn().mockReturnValue({ httpOnly: true, secure: false }),
  hashPassword: mockHashPassword,
  verifyPassword: mockVerifyPassword,
  signToken: mockSignToken,
}));

import {
  getSetupStatus,
  setup,
  login,
  logout,
  me,
} from "../controllers/auth.controller";

function mockReq(overrides?: Partial<Request>): Request {
  return {
    params: {},
    query: {},
    body: {},
    user: { id: 1, name: "Admin", email: "admin@test.com", role: "SUPERADMIN" as Role },
    ...overrides,
  } as Request;
}

function mockRes(): Response {
  const res = {} as Response;
  res.status = vi.fn().mockReturnValue(res);
  res.json = vi.fn().mockReturnValue(res);
  res.cookie = vi.fn().mockReturnValue(res);
  res.clearCookie = vi.fn().mockReturnValue(res);
  return res;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("getSetupStatus", () => {
  it("returns needs_setup=true when no accounts exist", async () => {
    mockPrisma.cSR.count.mockResolvedValue(0);
    const req = mockReq();
    const res = mockRes();
    await getSetupStatus(req, res);
    expect(res.json).toHaveBeenCalledWith({
      success: true,
      data: { needs_setup: true },
    });
  });

  it("returns needs_setup=false when accounts exist", async () => {
    mockPrisma.cSR.count.mockResolvedValue(1);
    const req = mockReq();
    const res = mockRes();
    await getSetupStatus(req, res);
    expect(res.json).toHaveBeenCalledWith({
      success: true,
      data: { needs_setup: false },
    });
  });
});

describe("setup", () => {
  it("creates the first SUPERADMIN account", async () => {
    mockPrisma.cSR.count.mockResolvedValue(0);
    mockPrisma.cSR.create.mockResolvedValue({
      id: 1,
      name: "Admin",
      email: "admin@test.com",
      role: "SUPERADMIN",
      password_hash: "hash",
      last_login_at: null,
      created_at: new Date(),
      updated_at: new Date(),
    });

    const req = mockReq({
      body: {
        name: "Admin",
        email: "admin@test.com",
        password: "password123",
      },
    });
    const res = mockRes();
    await setup(req, res);

    expect(mockHashPassword).toHaveBeenCalledWith("password123");
    expect(mockSignToken).toHaveBeenCalled();
    expect(res.cookie).toHaveBeenCalledWith("session", "jwt-token", expect.any(Object));
    expect(res.status).toHaveBeenCalledWith(201);
  });

  it("rejects setup when accounts already exist", async () => {
    mockPrisma.cSR.count.mockResolvedValue(1);
    const req = mockReq({
      body: {
        name: "Admin",
        email: "admin@test.com",
        password: "password123",
      },
    });
    const res = mockRes();
    await expect(setup(req, res)).rejects.toThrow(
      "Setup has already been completed"
    );
  });
});

describe("login", () => {
  const csr = {
    id: 1,
    name: "Admin",
    email: "admin@test.com",
    role: "SUPERADMIN" as Role,
    password_hash: "$2a$10$hash",
    failed_login_attempts: 0,
    locked_until: null,
    last_login_at: null,
    deleted_at: null,
    created_at: new Date(),
    updated_at: new Date(),
  };

  it("logs in with valid credentials", async () => {
    mockPrisma.cSR.findFirst.mockResolvedValue(csr);
    mockVerifyPassword.mockResolvedValue(true);
    mockPrisma.cSR.update.mockResolvedValue(csr);

    const req = mockReq({
      body: { email: "admin@test.com", password: "password123" },
    });
    const res = mockRes();
    await login(req, res);

    expect(mockVerifyPassword).toHaveBeenCalledWith("password123", csr.password_hash);
    expect(res.cookie).toHaveBeenCalled();
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ success: true })
    );
  });

  it("rejects invalid password", async () => {
    mockPrisma.cSR.findFirst.mockResolvedValue(csr);
    mockVerifyPassword.mockResolvedValue(false);

    const req = mockReq({
      body: { email: "admin@test.com", password: "wrong" },
    });
    const res = mockRes();
    await expect(login(req, res)).rejects.toThrow("Invalid email or password");
  });

  it("rejects login when account is locked", async () => {
    mockPrisma.cSR.findFirst.mockResolvedValue({
      ...csr,
      locked_until: new Date(Date.now() + 60000 * 10),
    });

    const req = mockReq({
      body: { email: "admin@test.com", password: "password123" },
    });
    const res = mockRes();
    await expect(login(req, res)).rejects.toThrow("Account temporarily locked");
  });

  it("locks account after max failed attempts", async () => {
    mockPrisma.cSR.findFirst.mockResolvedValue({
      ...csr,
      failed_login_attempts: 4,
    });
    mockVerifyPassword.mockResolvedValue(false);

    const req = mockReq({
      body: { email: "admin@test.com", password: "wrong" },
    });
    const res = mockRes();
    await expect(login(req, res)).rejects.toThrow(
      "Too many failed attempts"
    );
    expect(mockPrisma.cSR.update).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: 1 },
        data: expect.objectContaining({
          locked_until: expect.any(Date),
          failed_login_attempts: 0,
        }),
      })
    );
  });

  it("rejects login for non-existent email", async () => {
    mockPrisma.cSR.findFirst.mockResolvedValue(null);

    const req = mockReq({
      body: { email: "nobody@test.com", password: "password123" },
    });
    const res = mockRes();
    await expect(login(req, res)).rejects.toThrow("Invalid email or password");
  });
});

describe("logout", () => {
  it("clears the session cookie", async () => {
    const req = mockReq();
    const res = mockRes();
    await logout(req, res);
    expect(res.clearCookie).toHaveBeenCalledWith("session", expect.any(Object));
    expect(res.json).toHaveBeenCalledWith({ success: true });
  });
});

describe("me", () => {
  it("returns the current user", async () => {
    const req = mockReq();
    const res = mockRes();
    await me(req, res);
    expect(res.json).toHaveBeenCalledWith({
      success: true,
      data: req.user,
    });
  });
});
