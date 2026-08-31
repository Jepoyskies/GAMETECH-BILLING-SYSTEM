import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, ScrollText } from "lucide-react";
import api from "../lib/api";
import { useToast } from "../context/ToastContext";
import { useQuerySubscription } from "../lib/querySync";
import type { AuditLogEntry, CursorPagination } from "../lib/types";
import DateRangePicker from "../components/filters/DateRangePicker";
import SearchFilterInput from "../components/filters/SearchFilterInput";
import ExportMonthDropdown from "../components/filters/ExportMonthDropdown";
import { useCSR } from "../hooks/useCSR";
import "../styles/ListPage.css";
import "../styles/AuditLog.css";

const ACTIONS = ["", "CREATE", "UPDATE", "DELETE"];
const ENTITY_TYPES = ["", "CSR", "Customer", "Technician", "Team", "MonitoringRecord", "Dispatch", "ConfigOption", "MonthlyTarget"];

const actionClass: Record<string, string> = {
  CREATE: "audit-badge create",
  UPDATE: "audit-badge update",
  DELETE: "audit-badge delete",
};

type FieldChange = {
  path: string;
  before: unknown;
  after: unknown;
};

const DIFF_IGNORE_KEYS = new Set(["updated_at", "created_at"]);

const FIELD_LABELS: Record<string, Record<string, string>> = {
  CSR: {
    name: "Name",
    email: "Email",
    role: "Role",
    last_login_at: "Last Login",
    failed_login_attempts: "Failed Logins",
    locked_until: "Locked Until",
    deleted_at: "Deleted At",
  },
  Customer: {
    name: "Name",
    address: "Address",
    contact_number: "Contact #",
    email: "Email",
    barangay_city: "Barangay/City",
    latitude: "Latitude",
    longitude: "Longitude",
    deleted_at: "Deleted At",
  },
  Technician: {
    name: "Name",
  },
  Team: {
    name: "Team Name",
    deleted_at: "Deleted At",
  },
  MonitoringRecord: {
    tab_type: "Tab Type",
    date: "Date",
    client: "Client",
    address: "Address",
    contact_number: "Contact #",
    concern: "Concern",
    sales_agent: "Sales Agent",
    latitude: "Latitude",
    longitude: "Longitude",
    statusOption: "Status",
    typeOption: "Type",
    chatTypeOption: "Chat Type",
    remarks: "Remarks",
    ticket_number: "Ticket No.",
    actions_taken: "Actions Taken",
    time_start: "Service Start",
    time_accomplish: "Service End",
    done_at: "Date Completed",
    deleted_at: "Deleted At",
    customer_id: "Customer ID",
    teams: "Technicians",
    "jobDetail.schedule_date": "Schedule Date",
    "jobDetail.schedule_time": "Schedule Time",
    "jobDetail.barangay_city": "Barangay/City",
    "jobDetail.account_no": "Account #",
    "jobDetail.job_order": "Job Order",
    "jobDetail.email_address": "Email Address",
    "jobDetail.nap_port": "NAP Port",
    "jobDetail.cable_length": "Cable Length",
    "jobDetail.nap_reading": "NAP Reading",
    "jobDetail.pole_number": "Pole #",
    "jobDetail.plan_package": "Plan Package",
    "jobDetail.ont_modem_sn": "ONT/Modem S/N",
    "jobDetail.signal_level": "Signal Level",
    "jobDetail.facility": "Facility",
    "jobDetail.house_reading": "House Reading",
    "jobDetail.special_instruction": "Special Instruction",
    "jobDetail.technician_remarks": "Technician Remarks",
    "jobDetail.acknowledged_by": "Acknowledged By",
  },
  Dispatch: {
    date: "Date",
    client: "Client",
    address: "Address",
    contact_number: "Contact #",
    concern: "Concern",
    sales_agent: "Sales Agent",
    statusOption: "Status",
    typeOption: "Type",
    chatTypeOption: "Chat Type",
    latitude: "Latitude",
    longitude: "Longitude",
    remarks: "Remarks",
    time_start: "Service Start",
    time_accomplish: "Service End",
    done_at: "Date Completed",
    source_tab: "Source Tab",
    ticket_number: "Ticket No.",
    actions_taken: "Actions Taken",
    deleted_at: "Deleted At",
    customer_id: "Customer ID",
    monitoring_id: "Monitoring ID",
    teams: "Technicians",
    duration: "Service Duration",
    done_duration: "Done Duration",
  },
  ConfigOption: {
    list_type: "List Type",
    module: "Module",
    label: "Label",
    color: "Color",
    sort_order: "Sort Order",
    active: "Active",
    hardcoded: "Hardcoded",
    dispatch_equivalent_id: "Dispatch Equivalent",
    deleted_at: "Deactivated At",
  },
  MonthlyTarget: {
    month: "Month",
    year: "Year",
    target: "Target",
  },
};

const FIELD_ORDER: Record<string, string[]> = {
  CSR: ["name", "email", "role", "last_login_at", "failed_login_attempts", "locked_until", "deleted_at"],
  Customer: ["name", "address", "contact_number", "email", "barangay_city", "latitude", "longitude", "deleted_at"],
  Technician: ["name"],
  Team: ["name", "deleted_at"],
  MonitoringRecord: [
    "tab_type", "date", "client", "address", "contact_number", "concern",
    "sales_agent", "statusOption", "typeOption", "chatTypeOption",
    "latitude", "longitude",
    "teams",
    "time_start", "time_accomplish",
    "done_at", "remarks", "ticket_number", "actions_taken",
    "jobDetail.schedule_date", "jobDetail.schedule_time", "jobDetail.barangay_city",
    "jobDetail.account_no", "jobDetail.job_order", "jobDetail.email_address",
    "jobDetail.plan_package", "jobDetail.nap_port", "jobDetail.cable_length",
    "jobDetail.nap_reading", "jobDetail.pole_number", "jobDetail.ont_modem_sn",
    "jobDetail.signal_level", "jobDetail.facility", "jobDetail.house_reading",
    "jobDetail.special_instruction", "jobDetail.technician_remarks", "jobDetail.acknowledged_by",
    "deleted_at", "customer_id",
  ],
  Dispatch: [
    "date", "client", "address", "contact_number", "concern", "sales_agent",
    "statusOption", "typeOption", "chatTypeOption",
    "latitude", "longitude",
    "teams",
    "time_start", "time_accomplish", "done_at",
    "remarks", "ticket_number", "actions_taken",
    "source_tab", "duration", "done_duration",
    "deleted_at", "customer_id", "monitoring_id",
  ],
  ConfigOption: [
    "label", "list_type", "module", "color", "sort_order", "active", "hardcoded",
    "dispatch_equivalent_id", "deleted_at",
  ],
  MonthlyTarget: ["month", "year", "target"],
};

const HIDDEN_FIELDS: Record<string, Set<string>> = {
  CSR: new Set(["id", "failed_login_attempts", "locked_until"]),
  Customer: new Set(["id"]),
  Technician: new Set(),
  Team: new Set(["id"]),
  MonitoringRecord: new Set(["id", "customer_id"]),
  Dispatch: new Set(["id", "customer_id", "monitoring_id"]),
  ConfigOption: new Set(["id", "dispatch_equivalent_id"]),
  MonthlyTarget: new Set(["id"]),
};

function fieldLabel(entityType: string, path: string): string {
  return FIELD_LABELS[entityType]?.[path] ?? FIELD_LABELS["*"]?.[path] ?? path;
}

function sortChanges(entityType: string, changes: FieldChange[]): FieldChange[] {
  const order = FIELD_ORDER[entityType] ?? [];
  const orderMap = new Map(order.map((k, i) => [k, i]));
  return [...changes].sort((a, b) => {
    const ai = orderMap.get(a.path) ?? 999;
    const bi = orderMap.get(b.path) ?? 999;
    return ai - bi;
  });
}

function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") {
    if (value === "") return "(empty)";
    const ts = Date.parse(value);
    if (!isNaN(ts) && value.includes("T") && value.endsWith("Z")) {
      return new Date(value).toLocaleString();
    }
    return value;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "—";
    return value.map((v) => formatFieldValue(v)).join(", ");
  }
  if (isPlainObject(value)) {
    const entries = Object.entries(value)
      .filter(([, v]) => v !== null && v !== undefined)
      .map(([k, v]) => `${k}: ${formatFieldValue(v)}`);
    return entries.length ? entries.join("; ") : JSON.stringify(value);
  }
  return String(value);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNullish(value: unknown): boolean {
  return value === null || value === undefined;
}

function valuesEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (isNullish(a) && isNullish(b)) return true;
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false;
  }
}

function diffObjects(
  before: Record<string, unknown> | null | undefined,
  after: Record<string, unknown> | null | undefined,
  prefix = ""
): FieldChange[] {
  if (!isPlainObject(before) || !isPlainObject(after)) return [];

  const changes: FieldChange[] = [];
  const sharedKeys = Object.keys(before).filter((k) => k in after);

  for (const key of sharedKeys) {
    if (DIFF_IGNORE_KEYS.has(key)) continue;

    const path = prefix ? `${prefix}.${key}` : key;
    const beforeVal = before[key];
    const afterVal = after[key];

    if (valuesEqual(beforeVal, afterVal)) continue;

    if (isPlainObject(beforeVal) && isPlainObject(afterVal)) {
      changes.push(...diffObjects(beforeVal, afterVal, path));
      continue;
    }

    changes.push({ path, before: beforeVal, after: afterVal });
  }

  return changes;
}

function getChanges(log: AuditLogEntry): FieldChange[] {
  if (log.action === "CREATE") {
    return [];
  }
  if (log.action === "DELETE") {
    return [];
  }
  return diffObjects(
    log.before as Record<string, unknown> | null,
    log.after as Record<string, unknown> | null
  );
}

export default function AuditLog() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [pagination, setPagination] = useState<CursorPagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState<number | undefined>();
  const [cursorHistory, setCursorHistory] = useState<number[]>([]);

  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [actorId, setActorId] = useState("");
  const [summary, setSummary] = useState("");
  const [dateFrom, setDateFrom] = useState<string | undefined>();
  const [dateTo, setDateTo] = useState<string | undefined>();
  const [expanded, setExpanded] = useState<number | null>(null);

  const [rawView, setRawView] = useState<Record<number, boolean>>({});

  const tableWrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = tableWrapRef.current;
    if (!el) return;
    const SCROLL_SENSITIVITY = 1;
    const handleWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      el.scrollLeft = el.scrollLeft + e.deltaY * SCROLL_SENSITIVITY;
    };
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      el.removeEventListener("wheel", handleWheel);
    };
  }, []);

  const { addToast } = useToast();
  const { data: csrList } = useCSR();
  const isInitialLoad = useRef(true);

  useEffect(() => {
    if (error) addToast(error, "error");
  }, [error]);

  const pageCount = cursorHistory.length + 1;

  const load = useCallback(async () => {
    if (isInitialLoad.current) {
      setLoading(true);
    }
    setError(null);
    try {
      const params = new URLSearchParams();
      if (action) params.set("action", action);
      if (entityType) params.set("entity_type", entityType);
      if (actorId) params.set("actor", actorId);
      if (summary) params.set("summary", summary);
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (cursor) params.set("cursor", String(cursor));
      params.set("limit", "100");
      const res = await api.get(`/audit?${params.toString()}`);
      setLogs(res.data.data as AuditLogEntry[]);
      setPagination(res.data.pagination as CursorPagination);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit log");
    } finally {
      setLoading(false);
      isInitialLoad.current = false;
    }
  }, [action, entityType, actorId, summary, dateFrom, dateTo, cursor]);

  useQuerySubscription("auditLog", load);

  useEffect(() => {
    load();
  }, [load]);

  const handleNext = useCallback(() => {
    if (!pagination?.has_next || pagination.next_cursor === null) return;
    setCursorHistory((prev) => [...prev, cursor ?? 0]);
    setCursor(pagination.next_cursor);
  }, [pagination, cursor]);

  const handlePrev = useCallback(() => {
    setCursorHistory((prev) => {
      if (prev.length === 0) return prev;
      const newHistory = [...prev];
      const prevCursor = newHistory.pop()!;
      setCursor(prevCursor || undefined);
      return newHistory;
    });
  }, []);

  const toggleRaw = (id: number) => {
    setRawView((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const exportFilterParams = new URLSearchParams();
  if (action) exportFilterParams.set("action", action);
  if (entityType) exportFilterParams.set("entity_type", entityType);
  if (actorId) exportFilterParams.set("actor", actorId);

  return (
    <div className="list-page">
      <div className="list-header">
        <h1><ScrollText size={24} /> Audit Log</h1>
        <ExportMonthDropdown
          resourcePath="/audit"
          filePrefix="audit-log"
          filterParams={exportFilterParams}
        />
      </div>

      <div className="audit-filters">
        <DateRangePicker
            dateFrom={dateFrom}
            dateTo={dateTo}
            onChange={({ date_from, date_to }) => {
              setCursor(undefined);
              setCursorHistory([]);
              setDateFrom(date_from);
              setDateTo(date_to);
            }}
          />
          <select
            value={action}
            onChange={(e) => {
              setCursor(undefined);
              setCursorHistory([]);
              setAction(e.target.value);
            }}
          >
          {ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a || "All actions"}
            </option>
          ))}
        </select>
          <select
            value={entityType}
            onChange={(e) => {
              setCursor(undefined);
              setCursorHistory([]);
              setEntityType(e.target.value);
            }}
          >
            {ENTITY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t || "All record types"}
              </option>
            ))}
          </select>
          <select
            value={actorId}
            onChange={(e) => {
              setCursor(undefined);
              setCursorHistory([]);
              setActorId(e.target.value);
            }}
          >
          <option value="">All users</option>
          {csrList?.map((csr) => (
            <option key={csr.id} value={String(csr.id)}>
              {csr.name}
            </option>
          ))}
        </select>
        <div style={{ marginLeft: "auto" }}>
          <SearchFilterInput
            value={summary}
            placeholder="Search summary or Customer"
            onChange={(v) => {
              setCursor(undefined);
              setCursorHistory([]);
              setSummary(v ?? "");
            }}
          />
        </div>
      </div>

      {!loading && logs.length === 0 ? (
        <p className="period-meta" style={{ textAlign: "center" }}>No audit entries</p>
      ) : (
      <div className="audit-table-wrap" ref={tableWrapRef}>
        <table className="audit-table">
          <thead>
            <tr>
              <th style={{ width: "245px" }}>When</th>
              <th style={{ width: "140px" }}>Action</th>
              <th style={{ width: "240px" }}>Record</th>
              <th style={{ width: "165px" }}>Performed by</th>
              <th style={{ width: "300px" }}>Summary</th>
              <th style={{ width: "150px" }} />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="audit-empty">Loading…</td>
              </tr>
            ) : (
              logs.map((log) => {
                const isExpanded = expanded === log.id;
                const showRaw = !!rawView[log.id];
                const changes = isExpanded && !showRaw ? getChanges(log) : [];

                return (
                  <Fragment key={log.id}>
                    <tr>
                      <td>{new Date(log.created_at).toLocaleString()}</td>
                      <td>
                        <span className={actionClass[log.action] ?? "audit-badge"}>
                          {log.action}
                        </span>
                      </td>
                      <td>
                        {log.entity_type} #{log.entity_id}
                      </td>
                      <td>{log.actor?.name ?? `CSR #${log.actor_id}`}</td>
                      <td>{log.summary}</td>
                      <td>
                        <div className="audit-actions">
                          <button
                            className="audit-toggle"
                            title={isExpanded ? "Hide changes" : "Show changes"}
                            onClick={() =>
                              setExpanded(isExpanded ? null : log.id)
                            }
                          >
                            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                          </button>
                          {isExpanded && (
                            <button
                              className="audit-view-toggle"
                              onClick={() => toggleRaw(log.id)}
                            >
                              {showRaw ? "CLEAN" : "JSON"}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="audit-detail-row">
                        <td colSpan={6}>

                          {showRaw ? (
                            <div className="audit-diff">
                              <div>
                                <h4>Before</h4>
                                <pre>
                                  {log.before
                                    ? JSON.stringify(log.before, null, 2)
                                    : "—"}
                                </pre>
                              </div>
                              <div>
                                <h4>After</h4>
                                <pre>
                                  {log.after
                                    ? JSON.stringify(log.after, null, 2)
                                    : "—"}
                                </pre>
                              </div>
                            </div>
                          ) : log.action === "CREATE" ? (
                            <div className="audit-no-changes">
                              Record created — switch to raw JSON to see its full contents.
                            </div>
                          ) : log.action === "DELETE" ? (
                            <div className="audit-no-changes">
                              Record removed — switch to raw JSON to see its final state.
                            </div>
                          ) : changes.length === 0 ? (
                            <div className="audit-no-changes">
                              No field-level changes detected.
                            </div>
                          ) : (
                            <ul className="audit-changes-list">
                              {sortChanges(log.entity_type, changes)
                                .filter((c) => !(HIDDEN_FIELDS[log.entity_type]?.has(c.path)))
                                .map((change) => (
                                <li key={change.path} className="audit-change-item">
                                  <span className="audit-change-field">
                                    {fieldLabel(log.entity_type, change.path)}
                                  </span>
                                  <span className="audit-change-values">
                                    <span className="audit-change-value audit-change-before">
                                      {formatFieldValue(change.before)}
                                    </span>
                                    <span className="audit-change-arrow">→</span>
                                    <span className="audit-change-value audit-change-after">
                                      {formatFieldValue(change.after)}
                                    </span>
                                  </span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      )}

      {pagination && (cursorHistory.length > 0 || pagination.has_next) && (
        <div className="audit-pagination">
          <button disabled={cursorHistory.length === 0} onClick={handlePrev}>
            Previous
          </button>
          <span>Page {pageCount}</span>
          <button disabled={!pagination.has_next} onClick={handleNext}>
            Next
          </button>
        </div>
      )}
    </div>
  );
}