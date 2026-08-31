import { describe, it, expect } from "vitest";
import {
  DispatchQuerySchema,
  CreateMonitoringSchema,
  UpdateDispatchSchema,
  LoginSchema,
  SetupSchema,
  AuditQuerySchema,
  MarkDoneMonitoringSchema,
  CancelMonitoringSchema,
  CreateCustomerSchema,
  DeleteDispatchSchema,
  MonthlyTargetSchema,
} from "../lib/validators";

describe("LoginSchema", () => {
  it("accepts valid login credentials", () => {
    const result = LoginSchema.parse({
      email: "admin@example.com",
      password: "password123",
    });
    expect(result.email).toBe("admin@example.com");
    expect(result.password).toBe("password123");
  });

  it("normalizes email to lowercase", () => {
    const result = LoginSchema.parse({
      email: "Admin@Example.COM",
      password: "password123",
    });
    expect(result.email).toBe("admin@example.com");
  });

  it("rejects invalid email", () => {
    expect(() =>
      LoginSchema.parse({ email: "not-email", password: "password123" })
    ).toThrow();
  });

  it("rejects empty password", () => {
    expect(() =>
      LoginSchema.parse({ email: "admin@example.com", password: "" })
    ).toThrow();
  });
});

describe("SetupSchema", () => {
  it("accepts valid setup data", () => {
    const result = SetupSchema.parse({
      name: "Admin",
      email: "admin@example.com",
      password: "password123",
    });
    expect(result.name).toBe("Admin");
  });

  it("rejects short password for setup", () => {
    expect(() =>
      SetupSchema.parse({
        name: "Admin",
        email: "admin@example.com",
        password: "123",
      })
    ).toThrow();
  });
});

describe("DispatchQuerySchema", () => {
  it("provides defaults when no params", () => {
    const result = DispatchQuerySchema.parse({});
    expect(result.limit).toBe(50);
    expect(result.cursor).toBeUndefined();
  });

  it("parses cursor from string", () => {
    const result = DispatchQuerySchema.parse({ cursor: "123" });
    expect(result.cursor).toBe(123);
  });

  it("ignores cursor=0", () => {
    const result = DispatchQuerySchema.parse({ cursor: "0" });
    expect(result.cursor).toBeUndefined();
  });

  it("clamps limit to 150", () => {
    const result = DispatchQuerySchema.parse({ limit: "999" });
    expect(result.limit).toBe(150);
  });

  it("parses optional filters", () => {
    const result = DispatchQuerySchema.parse({
      status_id: "1",
      type_id: "2",
      csr: "3",
    });
    expect(result.status_id).toBe(1);
    expect(result.type_id).toBe(2);
    expect(result.csr).toBe(3);
  });

  it("parses team IDs from comma-separated string", () => {
    const result = DispatchQuerySchema.parse({ teams: "1,2,3" });
    expect(result.teams).toEqual([1, 2, 3]);
  });

  it("parses client search text", () => {
    const result = DispatchQuerySchema.parse({ client: "  John  " });
    expect(result.client).toBe("John");
  });

  it("accepts source_tab enum", () => {
    const result = DispatchQuerySchema.parse({ source_tab: "INTERNET_INSTALL" });
    expect(result.source_tab).toBe("INTERNET_INSTALL");
  });

  it("rejects invalid source_tab", () => {
    expect(() =>
      DispatchQuerySchema.parse({ source_tab: "INVALID" })
    ).toThrow();
  });
});

describe("AuditQuerySchema", () => {
  it("provides defaults when no params", () => {
    const result = AuditQuerySchema.parse({});
    expect(result.limit).toBe(30);
    expect(result.cursor).toBeUndefined();
  });

  it("parses cursor from string", () => {
    const result = AuditQuerySchema.parse({ cursor: "456" });
    expect(result.cursor).toBe(456);
  });

  it("accepts valid action", () => {
    const result = AuditQuerySchema.parse({ action: "CREATE" });
    expect(result.action).toBe("CREATE");
  });

  it("rejects invalid action", () => {
    expect(() => AuditQuerySchema.parse({ action: "INVALID" })).toThrow();
  });
});

describe("CreateMonitoringSchema", () => {
  const validRecord = {
    tab_type: "INTERNET_INSTALL",
    date: "2024-06-01",
    client: "John Doe",
    address: "123 Main St",
    contact_number: "09171234567",
    csr: 1,
    status_id: 1,
  };

  it("accepts a valid record", () => {
    const result = CreateMonitoringSchema.parse(validRecord);
    expect(result.client).toBe("John Doe");
    expect(result.tab_type).toBe("INTERNET_INSTALL");
  });

  it("accepts optional fields", () => {
    const result = CreateMonitoringSchema.parse({
      ...validRecord,
      concern: "Internet connection issue",
      sales_agent: "Jane",
      teams: [1, 2],
      latitude: 14.5,
      longitude: 121.0,
      type_id: 1,
      chat_type_id: 2,
    });
    expect(result.concern).toBe("Internet connection issue");
    expect(result.teams).toEqual([1, 2]);
  });

  it("rejects missing required fields", () => {
    expect(() => CreateMonitoringSchema.parse({})).toThrow();
  });

  it("rejects invalid tab_type", () => {
    expect(() =>
      CreateMonitoringSchema.parse({ ...validRecord, tab_type: "INVALID" })
    ).toThrow();
  });

  it("rejects empty client name", () => {
    expect(() =>
      CreateMonitoringSchema.parse({ ...validRecord, client: "" })
    ).toThrow();
  });
});

describe("UpdateDispatchSchema", () => {
  it("accepts partial updates", () => {
    const result = UpdateDispatchSchema.parse({ client: "Updated Name" });
    expect(result.client).toBe("Updated Name");
  });

  it("accepts empty object (no changes)", () => {
    const result = UpdateDispatchSchema.parse({});
    expect(Object.keys(result).length).toBe(0);
  });

  it("accepts status change", () => {
    const result = UpdateDispatchSchema.parse({ status_id: 5 });
    expect(result.status_id).toBe(5);
  });

  it("accepts teams array", () => {
    const result = UpdateDispatchSchema.parse({ teams: [1, 2, 3] });
    expect(result.teams).toEqual([1, 2, 3]);
  });
});

describe("MarkDoneMonitoringSchema", () => {
  it("accepts empty body", () => {
    const result = MarkDoneMonitoringSchema.parse({});
    expect(result.jobDetail).toBeUndefined();
  });

  it("accepts completion fields", () => {
    const result = MarkDoneMonitoringSchema.parse({
      jobDetail: {
        nap_port: "NAP-01",
        cable_length: "50m",
        ont_modem_sn: "SN12345",
      },
    });
    expect(result.jobDetail?.nap_port).toBe("NAP-01");
  });
});

describe("CancelMonitoringSchema", () => {
  it("requires a reason", () => {
    expect(() => CancelMonitoringSchema.parse({})).toThrow();
    expect(() => CancelMonitoringSchema.parse({ reason: "" })).toThrow();
  });

  it("accepts valid reason", () => {
    const result = CancelMonitoringSchema.parse({ reason: "Customer not available" });
    expect(result.reason).toBe("Customer not available");
  });

  it("rejects reason over 500 chars", () => {
    expect(() =>
      CancelMonitoringSchema.parse({ reason: "x".repeat(501) })
    ).toThrow();
  });
});

describe("CreateCustomerSchema", () => {
  it("accepts valid customer", () => {
    const result = CreateCustomerSchema.parse({
      name: "John Doe",
      address: "123 Main St",
      contact_number: "09171234567",
    });
    expect(result.name).toBe("John Doe");
  });

  it("rejects missing fields", () => {
    expect(() => CreateCustomerSchema.parse({ name: "John" })).toThrow();
  });
});

describe("DeleteDispatchSchema", () => {
  it("requires confirm_name", () => {
    expect(() => DeleteDispatchSchema.parse({})).toThrow();
  });

  it("accepts valid confirmation", () => {
    const result = DeleteDispatchSchema.parse({ confirm_name: "John" });
    expect(result.confirm_name).toBe("John");
  });
});

describe("MonthlyTargetSchema", () => {
  it("accepts valid target", () => {
    const result = MonthlyTargetSchema.parse({ month: 6, year: 2024, target: 100 });
    expect(result.month).toBe(6);
    expect(result.year).toBe(2024);
    expect(result.target).toBe(100);
  });

  it("rejects invalid month", () => {
    expect(() =>
      MonthlyTargetSchema.parse({ month: 13, year: 2024, target: 100 })
    ).toThrow();
  });

  it("rejects negative target", () => {
    expect(() =>
      MonthlyTargetSchema.parse({ month: 6, year: 2024, target: -1 })
    ).toThrow();
  });
});
