import { z } from "zod";

// ─── Enums ───────────────────────────────────────────────────────────────────

export const SourceTabEnum = z.enum([
  "INTERNET_INSTALL",
  "CIGNAL_PLAY",
  "CLIENT_CONCERNS",
]);

// ─── Map coordinates ─────────────────────────────────────────────────────────

const latitudeField = z.number().min(-90).max(90).optional().nullable();
const longitudeField = z.number().min(-180).max(180).optional().nullable();

// ─── Shared Transforms ───────────────────────────────────────────────────────

const coerceDate = z.string().transform((val) => {
  if (!val) return val;
  if (val.includes("T") && val.includes("Z")) return val;
  return new Date(val + "T00:00:00.000Z").toISOString();
});

const coerceTeams = z.array(z.number().int().positive()).transform((arr) =>
  [...new Set(arr.filter((t) => t > 0))]
);

const paginationFields = {
  page: z.string().optional().transform((v) => (v ? parseInt(v, 10) : 1)),
  limit: z.string().optional().transform((v) => (v ? Math.min(parseInt(v, 10), 150) : 50)),
};

const coerceOptionalPositiveInt = z
  .union([z.string(), z.number()])
  .optional()
  .transform((v) => {
    if (v === undefined || v === "") return undefined;
    const n = typeof v === "number" ? v : parseInt(v, 10);
    return Number.isFinite(n) && n > 0 ? n : undefined;
  });

const coerceSearchText = z
  .string()
  .optional()
  .transform((v) => {
    const trimmed = v?.trim();
    return trimmed ? trimmed.slice(0, 255) : undefined;
  });

const coerceTeamIds = z
  .string()
  .optional()
  .transform((v) => {
    if (!v) return undefined;
    const ids = v
      .split(",")
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => Number.isFinite(n) && n > 0);
    return ids.length > 0 ? [...new Set(ids)] : undefined;
  });

// ─── Auth ─────────────────────────────────────────────────────────────────────

const emailField = z
  .string()
  .min(1, "Email is required")
  .max(255)
  .email("Enter a valid email address")
  .transform((v) => v.trim().toLowerCase());

const passwordField = z
  .string()
  .min(8, "Password must be at least 8 characters")
  .max(128, "Password must be at most 128 characters");

export const SetupSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  email: emailField,
  password: passwordField,
});

export const LoginSchema = z.object({
  email: emailField,
  password: z.string().min(1, "Password is required").max(128),
});

export const CreateAccountSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  email: emailField,
  password: passwordField,
  current_password: z.string().min(1, "Your password is required to confirm"),
});

export const UpdatePasswordSchema = z.object({
  new_password: passwordField,
  current_password: z.string().min(1, "Current password is required").optional(),
});

export const UpdateAccountSchema = z.object({
  name: z.string().min(1, "Name is required").max(255).optional(),
  email: emailField.optional(),
});

// ─── CSR ─────────────────────────────────────────────────────────────────────

export const CreateCSRSchema = z.object({
  name: z.string().min(1, "CSR name is required").max(255),
});

export const UpdateCSRSchema = CreateCSRSchema.partial();

export const DeleteCSRSchema = z.object({
  confirm_name: z.string().min(1, "Confirmation name is required"),
});

// ─── Customer ────────────────────────────────────────────────────────────────

export const CreateCustomerSchema = z.object({
  name: z.string().min(1, "Customer name is required").max(255),
  address: z.string().min(1, "Address is required").max(500),
  contact_number: z.string().min(1, "Contact number is required").max(50),
  account_number: z.string().max(100).optional().nullable(),
  email: z.string().max(255).optional().nullable(),
  barangay_city: z.string().max(255).optional().nullable(),
  latitude: latitudeField,
  longitude: longitudeField,
});

export const UpdateCustomerSchema = CreateCustomerSchema.partial();

export const DeleteCustomerSchema = z.object({
  confirm_name: z.string().min(1, "Confirmation name is required"),
});

const CustomerSortEnum = z.enum(["name_asc", "created_desc"]);

export const CustomerQuerySchema = z.object({
  search: coerceSearchText,
  sort: CustomerSortEnum.optional().default("created_desc"),
  ...paginationFields,
});

export const CustomerSearchQuerySchema = z.object({
  q: coerceSearchText,
  limit: z
    .string()
    .optional()
    .transform((v) => (v ? Math.min(Math.max(parseInt(v, 10), 1), 20) : 8)),
});

// ─── Technician ──────────────────────────────────────────────────────────────

export const CreateTechnicianSchema = z.object({
  name: z.string().min(1, "Technician name is required").max(255),
  contact_number: z.string().max(50).optional().nullable(),
  target_per_day: z.number().int().min(0).default(0),
  target_per_month: z.number().int().min(0).default(0),
  team_id: z.number().int().positive().optional().nullable(),
});

export const UpdateTechnicianSchema = CreateTechnicianSchema.partial();

export const DeleteTechnicianSchema = z.object({
  confirm_name: z.string().min(1, "Confirmation name is required"),
});

// ─── Team ────────────────────────────────────────────────────────────────────

export const CreateTeamSchema = z.object({
  name: z.string().trim().min(1, "Team name is required").max(255),
});

export const UpdateTeamSchema = CreateTeamSchema.partial();

// ─── JobDetail (Install/Repair fields) ────────────────────────────────────────

const JobDetailPendingFields = z.object({
  schedule_date: z.string().optional().nullable(),
  schedule_time: z.string().optional().nullable(),
  barangay_city: z.string().optional().nullable(),
  account_no: z.string().optional().nullable(),
  job_order: z.string().optional().nullable(),
  email_address: z.string().optional().nullable(),
}).optional();

const JobDetailCompletionFields = z.object({
  nap_port: z.string().optional().nullable(),
  cable_length: z.string().optional().nullable(),
  nap_reading: z.string().optional().nullable(),
  pole_number: z.string().optional().nullable(),
  plan_package: z.string().optional().nullable(),
  ont_modem_sn: z.string().optional().nullable(),
  signal_level: z.string().optional().nullable(),
  facility: z.string().optional().nullable(),
  house_reading: z.string().optional().nullable(),
  special_instruction: z.string().optional().nullable(),
  technician_remarks: z.string().optional().nullable(),
  acknowledged_by: z.string().optional().nullable(),
}).optional();

const JobDetailAllFields = z.object({
  ...(JobDetailPendingFields.unwrap().shape),
  ...(JobDetailCompletionFields.unwrap().shape),
}).optional();

// ─── Dispatch ────────────────────────────────────────────────────────────────

export const CreateDispatchSchema = z.object({
  date: coerceDate,
  time: z.string().optional().nullable(),
  client: z.string().min(1, "Client name is required").max(255),
  address: z.string().min(1, "Address is required").max(500),
  contact_number: z.string().min(1, "Contact number is required").max(50),
  concern: z.string().min(1, "Concern is required"),
  sales_agent: z.string().min(1, "Sales agent is required").max(255),
  csr: z.number().int().positive("CSR ID must be a positive integer"),
  chat_type_id: z.number().int().positive(),
  type_id: z.number().int().positive(),
  status_id: z.number().int().positive(),
  remarks: z.string().optional().nullable(),
  time_start: z.string().optional().nullable(),
  time_accomplish: z.string().optional().nullable(),
  source_tab: SourceTabEnum,
  ticket_number: z.string().optional().nullable(),
  actions_taken: z.string().optional().nullable(),
  monitoring_id: z.number().int().positive().optional().nullable(),
  teams: coerceTeams.default([]),
  customer_id: z.number().int().positive().optional().nullable(),
  latitude: latitudeField,
  longitude: longitudeField,
});

export const UpdateDispatchSchema = z.object({
  date: coerceDate.optional(),
  time: z.string().optional().nullable(),
  client: z.string().min(1, "Client name is required").max(255).optional(),
  address: z.string().min(1, "Address is required").max(500).optional(),
  contact_number: z.string().min(1, "Contact number is required").max(50).optional(),
  concern: z.string().max(1000).optional().nullable(),
  sales_agent: z.string().max(255).optional().nullable(),
  csr: z.number().int().positive("CSR ID must be a positive integer").optional(),
  chat_type_id: z.number().int().positive().optional(),
  type_id: z.number().int().positive().optional(),
  status_id: z.number().int().positive().optional(),
  remarks: z.string().optional().nullable(),
  time_start: z.string().optional().nullable(),
  time_accomplish: z.string().optional().nullable(),
  done_at: z.string().optional().nullable(),
  source_tab: SourceTabEnum.optional(),
  ticket_number: z.string().optional().nullable(),
  actions_taken: z.string().optional().nullable(),
  teams: coerceTeams.optional(),
  customer_id: z.number().int().positive().optional().nullable(),
  latitude: latitudeField,
  longitude: longitudeField,
  jobDetail: JobDetailAllFields,
});

export const DeleteDispatchSchema = z.object({
  confirm_name: z.string().min(1, "Confirmation name is required"),
});

// ─── Monitoring ──────────────────────────────────────────────────────────────

export const CreateMonitoringSchema = z.object({
  tab_type: SourceTabEnum,
  date: coerceDate,
  time: z.string().optional().nullable(),
  client: z.string().min(1, "Client name is required").max(255),
  address: z.string().min(1, "Address is required").max(500),
  contact_number: z.string().min(1, "Contact number is required").max(50),
  concern: z.string().max(1000).optional().nullable(),
  sales_agent: z.string().max(255).optional().nullable(),
  csr: z.number().int().positive("CSR ID must be a positive integer"),
  type_id: z.number().int().positive().optional().nullable(),
  chat_type_id: z.number().int().positive().optional().nullable(),
  status_id: z.number().int().positive(),
  remarks: z.string().optional().nullable(),
  actions_taken: z.string().optional().nullable(),
  teams: coerceTeams.default([]),
  customer_id: z.number().int().positive().optional().nullable(),
  latitude: latitudeField,
  longitude: longitudeField,
  time_start: z.string().optional().nullable(),
  time_accomplish: z.string().optional().nullable(),
  jobDetail: JobDetailPendingFields,
});

export const UpdateMonitoringSchema = z.object({
  tab_type: SourceTabEnum.optional(),
  date: coerceDate.optional(),
  time: z.string().optional().nullable(),
  client: z.string().min(1, "Client name is required").max(255).optional(),
  address: z.string().min(1, "Address is required").max(500).optional(),
  contact_number: z.string().min(1, "Contact number is required").max(50).optional(),
  concern: z.string().max(1000).optional().nullable(),
  sales_agent: z.string().max(255).optional().nullable(),
  csr: z.number().int().positive("CSR ID must be a positive integer").optional(),
  type_id: z.number().int().positive().optional().nullable(),
  chat_type_id: z.number().int().positive().optional().nullable(),
  status_id: z.number().int().positive().optional(),
  remarks: z.string().optional().nullable(),
  actions_taken: z.string().optional().nullable(),
  teams: coerceTeams.optional(),
  customer_id: z.number().int().positive().optional().nullable(),
  latitude: latitudeField,
  longitude: longitudeField,
  time_start: z.string().optional().nullable(),
  time_accomplish: z.string().optional().nullable(),
  jobDetail: JobDetailPendingFields,
});

export const DeleteMonitoringSchema = z.object({
  confirm_name: z.string().min(1, "Confirmation name is required"),
});

export const MarkDoneMonitoringSchema = z.object({
  done_at: z.string().optional().nullable(),
  time_start: z.string().optional().nullable(),
  time_accomplish: z.string().optional().nullable(),
  teams: z.array(z.number()).optional(),
  jobDetail: JobDetailCompletionFields,
});

export const CancelMonitoringSchema = z.object({
  reason: z.string().min(1, "Reason is required").max(500),
});

// ─── Monthly Target ───────────────────────────────────────────────────────────

export const MonthlyTargetSchema = z.object({
  month: z.number().int().min(1).max(12),
  year: z.number().int().min(2020).max(2100),
  target: z.number().int().min(0),
});

// ─── Query Params ─────────────────────────────────────────────────────────────

export const DispatchQuerySchema = z.object({
  status_id: coerceOptionalPositiveInt,
  type_id: coerceOptionalPositiveInt,
  source_tab: SourceTabEnum.optional(),
  chat_type_id: coerceOptionalPositiveInt,
  csr: coerceOptionalPositiveInt,
  client: coerceSearchText,
  sales_agent: coerceSearchText,
  ticket_number: coerceSearchText,
  job_details: coerceSearchText,
  address: coerceSearchText,
  teams: coerceTeamIds,
  date_from: z.string().optional(),
  date_to: z.string().optional(),
  done_from: z.string().optional(),
  done_to: z.string().optional(),
  time_start_from: z.string().optional(),
  time_start_to: z.string().optional(),
  sort_by: z.enum(["date", "done_at"]).optional().default("date"),
  cursor: z
    .string()
    .optional()
    .transform((v) => {
      if (!v) return undefined;
      const n = parseInt(v, 10);
      return Number.isFinite(n) && n > 0 ? n : undefined;
    }),
  limit: paginationFields.limit,
});

export const MonitoringQuerySchema = z.object({
  tab_type: SourceTabEnum.optional(),
  status_id: coerceOptionalPositiveInt,
  type_id: coerceOptionalPositiveInt,
  csr: coerceOptionalPositiveInt,
  client: coerceSearchText,
  sales_agent: coerceSearchText,
  ticket_number: coerceSearchText,
  job_order: coerceSearchText,
  done: z
    .string()
    .optional()
    .transform((v) => (v === "true" ? true : v === "false" ? false : undefined)),
  ongoing: z
    .string()
    .optional()
    .transform((v) => (v === "true" ? true : v === "false" ? false : undefined)),
  date_from: z.string().optional(),
  date_to: z.string().optional(),
  ...paginationFields,
});

export const DashboardQuerySchema = z.object({
  date_from: z.string().optional(),
  date_to: z.string().optional(),
});

// ─── Config Options ───────────────────────────────────────────────────────────

export const ConfigListTypeEnum = z.enum(["STATUS", "TYPE", "CHAT_TYPE"]);

export const ConfigListModuleEnum = z.enum([
  "DISPATCH",
  "MONITORING",
]);

const hexColor = z
  .string()
  .regex(/^#([0-9A-Fa-f]{6})$/, "Color must be a valid hex code, e.g. #4F46E5");

export const CreateConfigOptionSchema = z.object({
  list_type: ConfigListTypeEnum,
  module: ConfigListModuleEnum,
  label: z.string().trim().min(1, "Label is required").max(100),
  color: hexColor,
});

export const UpdateConfigOptionSchema = z.object({
  label: z.string().trim().min(1).max(100).optional(),
  color: hexColor.optional(),
});

export const ReorderConfigOptionsSchema = z.object({
  list_type: ConfigListTypeEnum,
  module: ConfigListModuleEnum,
  ordered_ids: z.array(z.number().int().positive()).min(1),
});

export const ConfigOptionQuerySchema = z.object({
  list_type: ConfigListTypeEnum,
  module: ConfigListModuleEnum,
  include_inactive: z
    .string()
    .optional()
    .transform((v) => v === "true"),
});

// ─── Audit ────────────────────────────────────────────────────────────────────

export const AuditActionEnum = z.enum(["CREATE", "UPDATE", "DELETE"]);

export const AuditQuerySchema = z.object({
  action: AuditActionEnum.optional(),
  entity_type: z
    .enum([
      "CSR",
      "MonitoringRecord",
      "Dispatch",
      "Customer",
      "Technician",
      "Team",
      "ConfigOption",
      "MonthlyTarget",
    ])
    .optional(),
  entity_id: coerceOptionalPositiveInt,
  actor: coerceOptionalPositiveInt,
  summary: coerceSearchText,
  date_from: z.string().optional(),
  date_to: z.string().optional(),
  cursor: z
    .string()
    .optional()
    .transform((v) => {
      if (!v) return undefined;
      const n = parseInt(v, 10);
      return Number.isFinite(n) && n > 0 ? n : undefined;
    }),
  limit: z
    .string()
    .optional()
    .transform((v) => (v ? Math.min(parseInt(v, 10), 100) : 30)),
});