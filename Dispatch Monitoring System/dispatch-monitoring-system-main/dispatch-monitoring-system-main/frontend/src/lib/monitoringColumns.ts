import type { MonitoringRecord } from "./types";

export interface Column {
  key: string;
  header: string;
  width?: string;
  headerClassName?: string;
  render?: (row: MonitoringRecord) => React.ReactNode;
}

const dateTime = (row: MonitoringRecord, key: "date" | "time_start" | "time_accomplish") =>
  row[key]
    ? new Date(row[key] as string).toLocaleString(undefined, {
        year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit",
      })
    : "-";

const jd = (row: MonitoringRecord, field: keyof NonNullable<typeof row.jobDetail>) =>
  row.jobDetail?.[field] || "-";

export const COLUMN_REGISTRY: Record<string, Column> = {
  actions: { key: "actions", header: "Actions", width: "120px" },
  statusOption: { key: "statusOption", header: "Status", width: "120px" },
  date: { key: "date", header: "Date Created", width: "150px", render: (row) => dateTime(row, "date") },
  time_start: { key: "time_start", header: "Service Start", width: "165px", headerClassName: "th-highlight", render: (row) => dateTime(row, "time_start") },
  time_accomplish: { key: "time_accomplish", header: "Service End", width: "165px", headerClassName: "th-highlight", render: (row) => dateTime(row, "time_accomplish") },
  teams: { key: "teams", header: "Team", width: "250px", headerClassName: "th-highlight", render: (row) => row.teams?.map((t) => t.technician?.name).join(", ") || "-" },
  ticket_number: { key: "ticket_number", header: "Ticket No.", width: "150px" },
  client: { key: "client", header: "Client", width: "200px" },
  concern: { key: "concern", header: "Concern", width: "250px" },
  typeOption: { key: "typeOption", header: "Type", width: "120px" },
  chatTypeOption: { key: "chatTypeOption", header: "Chat Type", width: "120px" },
  csr: { key: "csr", header: "CSR", width: "185px", render: (row) => row.csr?.name },
  sales_agent: { key: "sales_agent", header: "Sales Agent", width: "150px" },
  actions_taken: { key: "actions_taken", header: "Actions Taken", width: "250px" },
  address: { key: "address", header: "Address", width: "300px" },
  contact_number: { key: "contact_number", header: "Contact", width: "140px" },
  remarks: { key: "remarks", header: "Remarks", width: "250px" },
  // JobDetail columns
  schedule_date: { key: "schedule_date", header: "Schedule Date", width: "130px", render: (row) => {
    const val = row.jobDetail?.schedule_date;
    if (!val) return "-";
    try { return new Date(val).toLocaleDateString(); } catch { return val; }
  } },
  schedule_time: { key: "schedule_time", header: "Schedule Time", width: "130px", render: (row) => {
    const val = row.jobDetail?.schedule_time;
    if (!val) return "-";
    const [h, m] = val.split(":");
    if (!h || !m) return val;
    const hour = parseInt(h, 10);
    const ampm = hour >= 12 ? "PM" : "AM";
    const hour12 = hour % 12 || 12;
    return `${hour12}:${m} ${ampm}`;
  } },
  account_no: { key: "account_no", header: "Account No.", width: "130px", render: (row) => jd(row, "account_no") },
  job_order: { key: "job_order", header: "Job Order No.", width: "130px", render: (row) => jd(row, "job_order") },
  barangay_city: { key: "barangay_city", header: "Barangay/City", width: "150px", render: (row) => jd(row, "barangay_city") },
  email_address: { key: "email_address", header: "Email", width: "180px", render: (row) => jd(row, "email_address") },
};

export function buildColumnsFromKeys(keys: string[]): Column[] {
  return keys.map((key) => {
    const col = COLUMN_REGISTRY[key];
    if (!col) throw new Error(`Unknown column key "${key}" — add it to COLUMN_REGISTRY.`);
    return col;
  });
}