export interface Technician {
  id: number;
  name: string;
  contact_number?: string | null;
  target_per_day: number;
  target_per_month: number;
  team_id?: number | null;
  team?: Team | null;
  created_at: string;
  updated_at: string;
}

export interface Team {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
  members?: Technician[];
}

export type Role = "SUPERADMIN" | "CSR_ADMIN";

export interface CSR {
  id: number;
  name: string;
  email?: string | null;
  role?: Role | null;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: Role;
  must_change_password: boolean;
}

export interface AuditLogEntry {
  id: number;
  action: "CREATE" | "UPDATE" | "DELETE";
  entity_type: string;
  entity_id: number;
  summary: string | null;
  before: unknown;
  after: unknown;
  actor_id: number;
  actor: { id: number; name: string; email: string | null; role: Role | null } | null;
  created_at: string;
}

export interface Customer {
  id: number;
  name: string;
  address: string;
  contact_number: string;
  account_number?: string | null;
  email?: string | null;
  barangay_city?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  deleted_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerSuggestion {
  id: number;
  name: string;
  address: string;
  contact_number: string;
  account_number?: string | null;
  email?: string | null;
  barangay_city?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface CustomerStats {
  total_jobs: number;
  dispatch_total: number;
  monitoring_total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
}

export interface CustomerJob {
  source: "DISPATCH" | "MONITORING";
  module: string;
  id: number;
  date: string;
  client: string;
  address: string;
  contact_number: string;
  concern: string;
  type: string | null;
  status: string;
  ticket_number: string | null;
  latitude?: number | null;
  longitude?: number | null;
  time_start: string | null;
  done_at: string | null;
}

export interface Pagination {
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface CursorPagination {
  next_cursor: number | null;
  has_next: boolean;
  limit: number;
}

export interface DispatchTeam {
  id: number;
  technician: Technician;
}

export interface MonitoringTeam {
  id: number;
  technician: Technician;
}

export interface Dispatch {
  id: number;
  date: string;
  client: string;
  address: string;
  contact_number: string;
  concern: string;
  sales_agent: string;
  csr: CSR;
  chat_type: string;
  type: string;
  status: string;
  status_id: number;
  type_id: number;
  chat_type_id: number;
  statusOption?: ConfigOption;
  typeOption?: ConfigOption;
  chatTypeOption?: ConfigOption;
  remarks: string | null;
  time_start: string | null;
  time_accomplish: string | null;
  duration: number | null;
  done_at: string | null;
  done_duration: number | null;
  source_tab: string;
  ticket_number: string | null;
  actions_taken: string | null;
  latitude?: number | null;
  longitude?: number | null;
  monitoring_id: number | null;
  monitoring?: { done_at: string | null; done_duration: number | null; jobDetail?: JobDetail | null } | null;
  customer_id: number | null;
  customer?: Customer | null;
  created_at: string;
  teams: DispatchTeam[];
}

export interface JobDetail {
  id: number;
  record_id: number;
  schedule_date: string | null;
  schedule_time: string | null;
  barangay_city: string | null;
  account_no: string | null;
  job_order: string | null;
  email_address: string | null;
  nap_port: string | null;
  cable_length: string | null;
  nap_reading: string | null;
  pole_number: string | null;
  plan_package: string | null;
  ont_modem_sn: string | null;
  signal_level: string | null;
  facility: string | null;
  house_reading: string | null;
  special_instruction: string | null;
  technician_remarks: string | null;
  acknowledged_by: string | null;
}

export interface MonitoringRecord {
  id: number;
  tab_type: string;
  type: string;
  type_id: number | null;
  chat_type_id: number | null;
  chatTypeOption?: ConfigOption;
  date: string;
  client: string;
  address: string;
  contact_number: string;
  concern: string;
  sales_agent: string | null;
  csr: CSR;
  status: string;
  status_id: number;
  statusOption?: ConfigOption;
  typeOption?: ConfigOption;
  remarks: string | null;
  ticket_number: string | null;
  actions_taken: string | null;
  latitude?: number | null;
  longitude?: number | null;
  customer_id: number | null;
  customer?: Customer | null;
  time_start: string | null;
  time_accomplish: string | null;
  done_at: string | null;
  done_duration: number | null;
  created_at: string;
  updated_at: string;
  teams: MonitoringTeam[];
  jobDetail?: JobDetail | null;
}

export type BackupType = "FULL" | "HOURLY";
export type BackupTrigger = "SCHEDULED" | "MANUAL";
export type BackupStatus = "SUCCESS" | "FAILED";

export interface BackupHistoryEntry {
  id: number;
  backup_type: BackupType;
  trigger_source: BackupTrigger;
  status: BackupStatus;
  filename: string;
  file_size: string | null;
  directory: string;
  error_message: string | null;
  restored_from_id: number | null;
  restored_by_id: number | null;
  created_at: string;
}

export type ConfigListType = "STATUS" | "TYPE" | "CHAT_TYPE";
export type ConfigListModule = "DISPATCH" | "MONITORING";

export interface ConfigOption {
  id: number;
  list_type: ConfigListType;
  module: ConfigListModule;
  label: string;
  color: string;
  sort_order: number;
  active: boolean;
  hardcoded: boolean;
  dispatch_equivalent: { id: number; label: string } | null;
}