import { Prisma, AuditAction } from "@prisma/client";
import logger from "./logger";

type AuditClient = Prisma.TransactionClient | {
  auditLog: { create: (args: { data: Prisma.AuditLogUncheckedCreateInput }) => unknown };
};

export type EntityType = "CSR" | "MonitoringRecord" | "Dispatch" | "Customer" | "Technician" | "Team" | "ConfigOption" | "MonthlyTarget";

interface WriteAuditInput {
  action: AuditAction;
  entity_type: EntityType;
  entity_id: number;
  actor_id: number;
  summary?: string;
  before?: unknown;
  after?: unknown;
}

const SENSITIVE_FIELDS = new Set(["password_hash", "password", "token"]);

const TECHNICIAN_NOISE_FIELDS = new Set([
  "contact_number",
  "target_per_day",
  "target_per_month",
  "created_at",
  "updated_at",
  "team_id",
]);

const CONFIG_OPTION_RELATION_FIELDS = new Set([
  "statusOption",
  "typeOption",
  "chatTypeOption",
  "csr",
]);
const CONFIG_OPTION_ID_FIELDS = new Set(["status_id", "type_id", "chat_type_id", "csr_id"]);

const JOIN_TABLE_SURROGATE_KEYS = new Set(["id", "dispatch_id", "technician_id", "record_id"]);

const DIFF_IGNORED_KEYS = new Set(["updated_at", "duration", "done_duration"]);

function isTechnicianShape(obj: Record<string, unknown>): boolean {
  return (
    "name" in obj &&
    "team_id" in obj &&
    !("client" in obj) &&
    !("status_id" in obj)
  );
}

function isDispatchTechnicianJoin(obj: Record<string, unknown>): boolean {
  return (
    "technician_id" in obj &&
    "dispatch_id" in obj &&
    Object.keys(obj).length <= 4
  );
}

function isNestedTechnicianArray(arr: unknown[]): boolean {
  if (arr.length === 0) return false;
  const first = arr[0];
  return (
    typeof first === "object" &&
    first !== null &&
    "technician" in (first as Record<string, unknown>)
  );
}

function sanitize(value: unknown): Prisma.InputJsonValue | typeof Prisma.JsonNull {
  if (value === null || value === undefined) return Prisma.JsonNull;

  const seen = new WeakSet<object>();

  const walk = (v: unknown): unknown => {
    if (v === null || v === undefined) return null;
    if (v instanceof Date) return v.toISOString();
    if (typeof v === "bigint") return v.toString();

    if (Array.isArray(v)) {
      if (isNestedTechnicianArray(v)) {
        return v.map((item) => {
          const obj = item as Record<string, unknown>;
          const tech = obj.technician as Record<string, unknown> | undefined;
          return typeof tech?.name === "string" ? tech.name : null;
        });
      }
      return v.map(walk);
    }

    if (typeof v === "object") {
      const obj = v as Record<string, unknown>;

      if (seen.has(obj)) return undefined;
      seen.add(obj);

      const out: Record<string, unknown> = {};
      const asTechnician = isTechnicianShape(obj);
      const asJoinRow = isDispatchTechnicianJoin(obj);

      for (const [k, val] of Object.entries(obj)) {
        if (SENSITIVE_FIELDS.has(k)) continue;

        if (DIFF_IGNORED_KEYS.has(k)) continue;

        if (CONFIG_OPTION_ID_FIELDS.has(k)) continue;

        if (JOIN_TABLE_SURROGATE_KEYS.has(k)) continue;

        if (CONFIG_OPTION_RELATION_FIELDS.has(k)) {
          const rel = val as Record<string, unknown> | null;
          const display = rel?.label ?? rel?.name;
          out[k] = typeof display === "string" ? display : null;
          continue;
        }

        if (asTechnician) {
          if (k === "name") out[k] = typeof val === "string" ? val : null;
          continue;
        }

        if (asJoinRow) {
          if (k === "technician" && typeof val === "object" && val !== null) {
            const tech = val as Record<string, unknown>;
            out[k] = typeof tech.name === "string" ? tech.name : null;
          }
          continue;
        }

        if (TECHNICIAN_NOISE_FIELDS.has(k)) continue;

        out[k] = walk(val);
      }

      return out;
    }

    return v;
  };

  return walk(value) as Prisma.InputJsonValue;
}

function normalizeForDiff(value: unknown): unknown {
  if (value === null || value === undefined || value === "") return null;

  if (value instanceof Date) {
    const d = new Date(value);
    d.setSeconds(0, 0);
    return d.toISOString();
  }

  if (Array.isArray(value)) {
    return value
      .map(normalizeForDiff)
      .sort((a, b) => {
        const aId = (a as Record<string, unknown>)?.id ?? 0;
        const bId = (b as Record<string, unknown>)?.id ?? 0;
        return Number(aId) - Number(bId);
      });
  }

  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(obj).sort()) {
      if (DIFF_IGNORED_KEYS.has(key)) continue;
      out[key] = normalizeForDiff(obj[key]);
    }
    return out;
  }

  return value;
}

export function hasMeaningfulChange(before: unknown, after: unknown): boolean {
  return (
    JSON.stringify(normalizeForDiff(before)) !==
    JSON.stringify(normalizeForDiff(after))
  );
}

export async function writeAudit(
  client: AuditClient,
  input: WriteAuditInput
): Promise<void> {
  if (
    input.action === "UPDATE" &&
    input.before !== undefined &&
    input.after !== undefined &&
    !hasMeaningfulChange(input.before, input.after)
  ) {
    return;
  }

  try {
    await client.auditLog.create({
      data: {
        action: input.action,
        entity_type: input.entity_type,
        entity_id: input.entity_id,
        actor_id: input.actor_id,
        summary: input.summary ?? null,
        before: sanitize(input.before),
        after: sanitize(input.after),
      },
    });
  } catch (err) {
    logger.error(
      { err, action: input.action, entityType: input.entity_type, entityId: input.entity_id, actorId: input.actor_id },
      "Failed to write audit log"
    );
  }
}