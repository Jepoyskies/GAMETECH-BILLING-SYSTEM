import { useState, useEffect, useRef } from "react";
import { Copy, Check } from "lucide-react";
import { useCSR } from "../hooks/useCSR";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useConfigOptions } from "../hooks/useConfigOptions";
import type { MonitoringRecord, CustomerSuggestion, ConfigListModule } from "../lib/types";
import api from "../lib/api";
import ClientAutocomplete from "./ClientAutocomplete";
import LocationField from "./map/LocationField";
import BarangayCityAutocomplete from "./BarangayCityAutocomplete";
import "../styles/Forms.css";

interface MonitoringFormProps {
  record?: MonitoringRecord | null;
  tabType?: string;
  onSubmit: (data: MonitoringFormData) => void;
  onCancel: () => void;
  onDelete?: () => void;
  onEdit?: () => void;
  loading?: boolean;
  readOnly?: boolean;
  ongoing?: boolean;
}

export interface MonitoringFormData {
  date: string;
  time: string;
  client: string;
  address: string;
  contact_number: string;
  concern: string;
  sales_agent: string;
  csr: number;
  status_id: number;
  type_id: number | null;
  chat_type_id: number | null;
  remarks: string;
  ticket_number: string;
  actions_taken: string;
  tab_type?: string;
  customer_id?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  teams?: number[];
  jobDetail?: {
    schedule_date?: string | null;
    schedule_time?: string | null;
    barangay_city?: string | null;
    account_no?: string | null;
    job_order?: string | null;
    email_address?: string | null;
  };
}

function toLocalTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function toDateOnly(value: string | null | undefined): string | null {
  if (!value) return null;
  const match = value.match(/^\d{4}-\d{2}-\d{2}/);
  if (match) return match[0];
  const d = new Date(value);
  if (isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 10);
}

export default function MonitoringForm({
  record,
  tabType,
  onSubmit,
  onCancel,
  onDelete,
  loading,
  readOnly = false,
  onEdit,
  ongoing = false,
}: MonitoringFormProps) {
  const { addToast } = useToast();
  const { user, isSuperAdmin } = useAuth();
  const { data: csrs } = useCSR();
  const statusModule = tabType === "DISPATCH" ? "DISPATCH" : "MONITORING";
  const statusOptions = useConfigOptions("STATUS", statusModule as ConfigListModule, true);
  const typeOptions = useConfigOptions("TYPE", "DISPATCH" as ConfigListModule, true);
  const chatTypeOptions = useConfigOptions("CHAT_TYPE", "DISPATCH" as ConfigListModule, true);

  const [editing, setEditing] = useState(!readOnly);
  const [customerId, setCustomerId] = useState<number | null>(record?.customer_id ?? null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [nameError, setNameError] = useState("");
  const [copied, setCopied] = useState(false);

  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const currentTime = `${pad(now.getHours())}:${pad(now.getMinutes())}`;

  const jd = record?.jobDetail;

  const [form, setForm] = useState<MonitoringFormData>({
    date: record?.date
      ? new Date(record.date).toISOString().slice(0, 10)
      : now.toISOString().slice(0, 10),
    time: record?.date ? toLocalTime(record.date) : currentTime,
    client: record?.client || "",
    address: record?.address || "",
    contact_number: record?.contact_number || "",
    concern: record?.concern || "",
    sales_agent: record?.sales_agent || "",
    csr: record?.csr?.id || user?.id || 0,
    status_id: record?.statusOption?.id ?? 0,
    chat_type_id: record?.chatTypeOption?.id ?? record?.chat_type_id ?? null,
    remarks: record?.remarks || "",
    ticket_number: record?.ticket_number || "",
    actions_taken: record?.actions_taken || "",
    tab_type: record?.tab_type || tabType || "INTERNET_INSTALL",
    type_id: record?.typeOption?.id ?? null,
    latitude: record?.latitude ?? null,
    longitude: record?.longitude ?? null,
    jobDetail: {
      schedule_date: toDateOnly(jd?.schedule_date),
      schedule_time: jd?.schedule_time ?? null,
      barangay_city: jd?.barangay_city ?? null,
      account_no: jd?.account_no ?? null,
      job_order: jd?.job_order ?? null,
      email_address: jd?.email_address ?? null,
    },
  });

  const initialFormRef = useRef(JSON.stringify(form));

  useEffect(() => {
    initialFormRef.current = JSON.stringify(form);
  }, [readOnly]);

  const hasChanges = JSON.stringify(form) !== initialFormRef.current;

  useEffect(() => {
    setEditing(!readOnly);
  }, [readOnly]);

  useEffect(() => {
    if (!record && form.status_id === 0 && statusOptions.options.length > 0) {
      const pending = statusOptions.options.find(
        (opt) => opt.label === "Pending"
      );
      if (pending) {
        setForm((f) => ({ ...f, status_id: pending.id }));
      }
    }
  }, [statusOptions.options, record, form.status_id]);

  const updateField = <K extends keyof MonitoringFormData>(
    field: K,
    value: MonitoringFormData[K]
  ) => {
    setForm((f) => ({ ...f, [field]: value }));
  };

  const checkName = async (value: string) => {
    if (!value.trim()) {
      setNameError("");
      return;
    }
    try {
      const params = new URLSearchParams({ name: value.trim() });
      if (customerId) params.set("exclude_id", String(customerId));
      const res = await api.get(`/customers/check-name?${params}`);
      if (res.data.data.exists) {
        setNameError("Customer name already exists");
      } else {
        setNameError("");
      }
    } catch {
      setNameError("");
    }
  };

  const handleClientSelect = (customer: CustomerSuggestion) => {
    setCustomerId(customer.id);
    setNameError("");
    setForm((f) => ({
      ...f,
      client: customer.name,
      address: customer.address,
      contact_number: customer.contact_number,
      latitude: customer.latitude ?? null,
      longitude: customer.longitude ?? null,
      jobDetail: {
        ...f.jobDetail,
        email_address: customer.email ?? f.jobDetail?.email_address ?? null,
        barangay_city: customer.barangay_city ?? f.jobDetail?.barangay_city ?? null,
        account_no: customer.account_number ?? f.jobDetail?.account_no ?? null,
      },
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;

    const newErrors: Record<string, string> = {};

    if (!form.date) newErrors.date = "Date is required";
    if (!form.client) newErrors.client = "Client is required";
    if (!form.address) newErrors.address = "Address is required";
    if (!form.contact_number) newErrors.contact_number = "Contact number is required";
    if (!form.csr) newErrors.csr = "CSR is required";
    if (!record && !form.type_id) newErrors.type_id = "Dispatch type is required";
    if (!form.chat_type_id) newErrors.chat_type_id = "Chat type is required";
    if (!form.status_id) newErrors.status_id = "Status is required";

    if (nameError) {
      addToast("Please fix the customer name error before saving", "error");
      return;
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      addToast("Please fill in all required fields", "error");
      return;
    }

    const payload: MonitoringFormData = { ...form, customer_id: customerId };

    if (!record) {
      payload.teams = [];
    }

    setErrors({});
    onSubmit(payload);
  };

  const updateJobDetail = (field: string, value: string | null) => {
    setForm((f) => ({
      ...f,
      jobDetail: { ...f.jobDetail, [field]: value || null },
    }));
  };

  const isInstallRepair = form.tab_type === "INTERNET_INSTALL" || form.tab_type === "CIGNAL_PLAY";
  const isConcernsTab = form.tab_type === "CLIENT_CONCERNS";
  const isDispatchTab = form.tab_type === "DISPATCH";
  const isNewRecord = !record;

  // Auto-select "Installation" type and "For Installation" chat type for install/repair tabs
  useEffect(() => {
    if (isInstallRepair && !record) {
      const installationType = typeOptions.options.find((o) => o.label === "Installation");
      const forInstallationChatType = chatTypeOptions.options.find((o) => o.label === "For Installation");
      if (installationType) {
        setForm((f) => ({ ...f, type_id: installationType.id }));
      }
      if (forInstallationChatType) {
        setForm((f) => ({ ...f, chat_type_id: forInstallationChatType.id }));
      }
    }
  }, [isInstallRepair, record, typeOptions.options, chatTypeOptions.options]);

  // Auto-select "Repair" type and "Concern" chat type for client concerns tab
  useEffect(() => {
    if (isConcernsTab && !record) {
      const repairType = typeOptions.options.find((o) => o.label === "Repair");
      const concernChatType = chatTypeOptions.options.find((o) => o.label === "Concern");
      if (repairType) {
        setForm((f) => ({ ...f, type_id: repairType.id }));
      }
      if (concernChatType) {
        setForm((f) => ({ ...f, chat_type_id: concernChatType.id }));
      }
    }
  }, [isConcernsTab, record, typeOptions.options, chatTypeOptions.options]);

  const filteredTypeOptions = isConcernsTab
    ? typeOptions.options.filter((o) => o.label !== "Installation")
    : typeOptions.options;
  const filteredChatTypeOptions = isConcernsTab
    ? chatTypeOptions.options.filter((o) => o.label !== "For Installation")
    : chatTypeOptions.options;
  const jdCompletion = record?.jobDetail;
  const hasCompletionData = jdCompletion && (
    jdCompletion.nap_port || jdCompletion.cable_length || jdCompletion.nap_reading ||
    jdCompletion.pole_number || jdCompletion.plan_package || jdCompletion.ont_modem_sn ||
    jdCompletion.signal_level || jdCompletion.facility || jdCompletion.house_reading ||
    jdCompletion.special_instruction || jdCompletion.technician_remarks || jdCompletion.acknowledged_by
  );
  const disabled = !editing;
  const dispatchLocked = editing && ongoing;

  const title = isNewRecord
    ? "New Record"
    : editing
      ? "Edit Record"
      : `Record #${record?.id}`;

  const [uptime, setUptime] = useState<string | null>(null);

  useEffect(() => {
    if (!record || record.done_at || !record.date) { setUptime(null); return; }
    const from = new Date(record.date).getTime();
    if (isNaN(from)) { setUptime(null); return; }
    const update = () => {
      const diffMinutes = Math.round((Date.now() - from) / 60000);
      if (diffMinutes < 0) { setUptime(null); return; }
      const days = Math.floor(diffMinutes / (60 * 24));
      const hours = Math.floor((diffMinutes % (60 * 24)) / 60);
      const minutes = diffMinutes % 60;
      const parts = [];
      if (days > 0) parts.push(`${days}d`);
      if (hours > 0) parts.push(`${hours}h`);
      if (minutes > 0 || parts.length === 0) parts.push(`${minutes}m`);
      setUptime(parts.join(" "));
    };
    update();
    const id = setInterval(update, 60000);
    return () => clearInterval(id);
  }, [record]);

  return (
    <form className="form-modal" onSubmit={handleSubmit}>
      <div className="form-header" style={{ display: "flex", alignItems: "center" }}>
        <h2>{title}</h2>
        {uptime && <span style={{ marginLeft: "auto", fontSize: "0.8rem", color: "#666" }}>Uptime: {uptime}</span>}
      </div>

      <div className="form-body">

        {/* ── Job Info ── */}
        <div className="section-divider">
          <span className="section-divider-label">Job Info</span>
        </div>
        {(isInstallRepair || isConcernsTab) && (
          <div className="form-row-group">
            <div className="form-row">
              <label>Job Order No.</label>
              <input
                type="text"
                value={form.jobDetail?.job_order || ""}
                onChange={(e) => updateJobDetail("job_order", e.target.value)}
                disabled={disabled}

              />
            </div>
            <div className="form-row">
              <label>Date Created <span className="required">*</span></label>
              {isNewRecord ? (
                <input
                  type="datetime-local"
                  value={form.date && form.time ? `${form.date}T${form.time}` : ""}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value) {
                      const [datePart, timePart] = value.split("T");
                      updateField("date", datePart);
                      updateField("time", timePart?.slice(0, 5) || "");
                    }
                    setErrors((prev) => { const next = { ...prev }; delete next.date; return next; });
                  }}
                  disabled={disabled || (dispatchLocked && !isNewRecord)}
                  required
                />
              ) : (
                <input
                  type="datetime-local"
                  value={form.date && form.time ? `${form.date}T${form.time}` : ""}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value) {
                      const [datePart, timePart] = value.split("T");
                      updateField("date", datePart);
                      updateField("time", timePart);
                    }
                  }}
                  disabled={disabled || dispatchLocked}
                  required
                />
              )}
              {errors.date && <div className="form-field-error">{errors.date}</div>}
            </div>
          </div>
        )}
        {isDispatchTab && (
          <div className="form-row">
            <label>Date Created <span className="required">*</span></label>
            {isNewRecord ? (
              <input
                type="datetime-local"
                value={form.date && form.time ? `${form.date}T${form.time}` : ""}
                onChange={(e) => {
                  const value = e.target.value;
                  if (value) {
                    const [datePart, timePart] = value.split("T");
                    updateField("date", datePart);
                    updateField("time", timePart?.slice(0, 5) || "");
                  }
                  setErrors((prev) => { const next = { ...prev }; delete next.date; return next; });
                }}
                disabled={disabled}
                required
              />
            ) : (
              <input
                type="datetime-local"
                value={form.date && form.time ? `${form.date}T${form.time}` : ""}
                onChange={(e) => {
                  const value = e.target.value;
                  if (value) {
                    const [datePart, timePart] = value.split("T");
                    updateField("date", datePart);
                    updateField("time", timePart);
                  }
                }}
                disabled={disabled || dispatchLocked}
                required
              />
            )}
            {errors.date && <div className="form-field-error">{errors.date}</div>}
          </div>
        )}
        <div className="form-row-group">
          <div className="form-row">
            <label>Type <span className="required">*</span></label>
            <select
              className={isInstallRepair ? "select-locked" : ""}
              value={form.type_id ?? ""}
              onChange={(e) => { updateField("type_id", Number(e.target.value)); setErrors((prev) => { const next = { ...prev }; delete next.type_id; return next; }); }}
              disabled={disabled || dispatchLocked || isInstallRepair || typeOptions.loading}
              required={isNewRecord}
            >
              <option value={0}>Select Type</option>
              {filteredTypeOptions.filter((o) => o.active).map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
            {errors.type_id && <div className="form-field-error">{errors.type_id}</div>}
          </div>
          <div className="form-row">
            <label>Chat Type <span className="required">*</span></label>
            <select
              value={form.chat_type_id ?? ""}
              onChange={(e) => { updateField("chat_type_id", Number(e.target.value) || null); setErrors((prev) => { const next = { ...prev }; delete next.chat_type_id; return next; }); }}
              disabled={disabled || dispatchLocked || chatTypeOptions.loading}
              required
            >
              <option value="">Select Chat Type</option>
              {filteredChatTypeOptions.filter((o) => o.active).map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
            {errors.chat_type_id && <div className="form-field-error">{errors.chat_type_id}</div>}
          </div>
        </div>
        <div className="form-row">
          <label>Status <span className="required">*</span></label>
            <select
              value={form.status_id}
              onChange={(e) => { updateField("status_id", Number(e.target.value)); setErrors((prev) => { const next = { ...prev }; delete next.status_id; return next; }); }}
              disabled={disabled || dispatchLocked || statusOptions.loading}
            >
              <option value={0}>Select Status</option>
              {statusOptions.options.filter((o) => o.active).map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          {errors.status_id && <div className="form-field-error">{errors.status_id}</div>}
        </div>

        {/* ── Subscriber Info ── */}
        <div className="section-divider">
          <span className="section-divider-label">Subscriber Info</span>
        </div>
        <div className="form-row-group">
          <div className="form-row">
            <label>Client <span className="required">*</span></label>
            <ClientAutocomplete
              value={form.client}
              onChange={(value) => { updateField("client", value); setErrors((prev) => { const next = { ...prev }; delete next.client; return next; }); setNameError(""); }}
              onSelect={handleClientSelect}
              onBlur={() => checkName(form.client)}
              className={nameError ? "field-error" : ""}
              disabled={disabled}
              required
            />
            {errors.client && <div className="form-field-error">{errors.client}</div>}
            {nameError && <div className="form-field-error">{nameError}</div>}
          </div>
          <div className="form-row">
            <label>Contact Number <span className="required">*</span></label>
            <input
              type="text"
              value={form.contact_number}
              onChange={(e) => { updateField("contact_number", e.target.value); setErrors((prev) => { const next = { ...prev }; delete next.contact_number; return next; }); }}
              disabled={disabled}

              required
            />
            {errors.contact_number && <div className="form-field-error">{errors.contact_number}</div>}
          </div>
        </div>
        <div className="form-row-group">
          <div className="form-row">
            <label>Account No.</label>
            <input
              type="text"
              value={form.jobDetail?.account_no || ""}
              onChange={(e) => updateJobDetail("account_no", e.target.value)}
              disabled={disabled}

            />
          </div>
          <div className="form-row">
            <label>Email Address</label>
            <input
              type="email"
              value={form.jobDetail?.email_address || ""}
              onChange={(e) => updateJobDetail("email_address", e.target.value)}
              disabled={disabled}

            />
          </div>
        </div>

        {/* ── Location ── */}
        <div className="section-divider">
          <span className="section-divider-label">Location</span>
        </div>
        <div className="form-row">
          <label>Address <span className="required">*</span></label>
          <LocationField
            latitude={form.latitude}
            longitude={form.longitude}
            address={form.address}
            disabled={disabled}
            required
            onChange={(loc) =>
              setForm((f) => ({
                ...f,
                latitude: loc?.latitude ?? null,
                longitude: loc?.longitude ?? null,
              }))
            }
            onAddressChange={(address) => { updateField("address", address); setErrors((prev) => { const next = { ...prev }; delete next.address; return next; }); }}
          />
        </div>
        <div className="form-row">
          <label>Barangay/City</label>
          <BarangayCityAutocomplete
            value={form.jobDetail?.barangay_city || ""}
            onChange={(v) => updateJobDetail("barangay_city", v)}
            disabled={disabled}
          />
        </div>

        {/* ── Scheduling ── */}
        <div className="section-divider">
          <span className="section-divider-label">Scheduling</span>
        </div>
        {(isInstallRepair || isConcernsTab) && (
          <div className="form-row-group">
            <div className="form-row">
              <label>Schedule Date</label>
              <input
                type="date"
                value={form.jobDetail?.schedule_date || ""}
                onChange={(e) => updateJobDetail("schedule_date", e.target.value)}
                disabled={disabled || dispatchLocked}
              />
            </div>
            <div className="form-row">
              <label>Schedule Time</label>
              <div className="time-input-wrapper">
                <input
                  type="time"
                  value={form.jobDetail?.schedule_time || ""}
                  onChange={(e) => updateJobDetail("schedule_time", e.target.value)}
                  disabled={disabled || dispatchLocked}
                />
                <button type="button" className="time-clear-btn" onClick={() => updateJobDetail("schedule_time", "")} disabled={disabled || dispatchLocked || !form.jobDetail?.schedule_time} title="Clear time">
                  ×
                </button>
              </div>
            </div>
          </div>
        )}
        <div className="form-row-group">
          <div className="form-row">
            <label>CSR <span className="required">*</span></label>
            <select
              value={form.csr}
              onChange={(e) => { updateField("csr", Number(e.target.value)); setErrors((prev) => { const next = { ...prev }; delete next.csr; return next; }); }}
              disabled={disabled || dispatchLocked}
              required
            >
              <option value={0}>Select CSR</option>
              {csrs.map((csr) => (
                <option key={csr.id} value={csr.id}>
                  {csr.name}
                </option>
              ))}
            </select>
            {errors.csr && <div className="form-field-error">{errors.csr}</div>}
          </div>
          {!isConcernsTab && (
            <div className="form-row">
              <label>Sales Agent</label>
              <input
                type="text"
                value={form.sales_agent}
                onChange={(e) => updateField("sales_agent", e.target.value)}
                disabled={disabled || dispatchLocked}

              />
            </div>
          )}
        </div>

        {/* ── Issue ── */}
        <div className="section-divider">
          <span className="section-divider-label">Issue</span>
        </div>
        <div className="form-row">
          <label>Concern / Problem Reported</label>
          <textarea
            value={form.concern}
            onChange={(e) => updateField("concern", e.target.value)}
            disabled={disabled}

          />
        </div>

        {/* ── Notes ── */}
        <div className="section-divider">
          <span className="section-divider-label">Notes</span>
        </div>
        <div className="form-row">
          <label>Remarks</label>
          <textarea
            value={form.remarks}
            onChange={(e) => updateField("remarks", e.target.value)}
            disabled={disabled}

          />
        </div>

        {/* ── Ticket Number (concerns only) ── */}
        {isConcernsTab && (
          <div className="form-row">
            <label>Ticket No.</label>
            <input
              type="text"
              value={form.ticket_number}
              readOnly
              placeholder="Auto-generated"
              disabled
            />
          </div>
        )}

        {/* ── Completion Details (read-only, shown when record has completion data) ── */}
        {!isNewRecord && hasCompletionData && (
          <>
            <div className="section-divider">
              <span className="section-divider-label">Completion Details</span>
            </div>

            <dl className="detail-list">
              {jdCompletion.nap_port && (
                <div className="detail-item">
                  <dt>NAP/Port</dt>
                  <dd>{jdCompletion.nap_port}</dd>
                </div>
              )}
              {jdCompletion.cable_length && (
                <div className="detail-item">
                  <dt>Cable Length</dt>
                  <dd>{jdCompletion.cable_length}</dd>
                </div>
              )}
              {jdCompletion.nap_reading && (
                <div className="detail-item">
                  <dt>NAP Reading</dt>
                  <dd>{jdCompletion.nap_reading}</dd>
                </div>
              )}
              {jdCompletion.pole_number && (
                <div className="detail-item">
                  <dt>Pole Number</dt>
                  <dd>{jdCompletion.pole_number}</dd>
                </div>
              )}
              {jdCompletion.plan_package && (
                <div className="detail-item">
                  <dt>Plan/Package</dt>
                  <dd>{jdCompletion.plan_package}</dd>
                </div>
              )}
              {jdCompletion.ont_modem_sn && (
                <div className="detail-item">
                  <dt>ONT/Modem SN</dt>
                  <dd>{jdCompletion.ont_modem_sn}</dd>
                </div>
              )}
              {jdCompletion.signal_level && (
                <div className="detail-item">
                  <dt>Signal Level</dt>
                  <dd>{jdCompletion.signal_level}</dd>
                </div>
              )}
              {jdCompletion.facility && (
                <div className="detail-item">
                  <dt>Facility</dt>
                  <dd>{jdCompletion.facility}</dd>
                </div>
              )}
              {jdCompletion.house_reading && (
                <div className="detail-item">
                  <dt>House Reading</dt>
                  <dd>{jdCompletion.house_reading}</dd>
                </div>
              )}
              {jdCompletion.special_instruction && (
                <div className="detail-item">
                  <dt>Special Instruction</dt>
                  <dd>{jdCompletion.special_instruction}</dd>
                </div>
              )}
              {jdCompletion.technician_remarks && (
                <div className="detail-item">
                  <dt>Technician Remarks</dt>
                  <dd>{jdCompletion.technician_remarks}</dd>
                </div>
              )}
              {jdCompletion.acknowledged_by && (
                <div className="detail-item">
                  <dt>Acknowledged By</dt>
                  <dd>{jdCompletion.acknowledged_by}</dd>
                </div>
              )}
            </dl>
          </>
        )}
      </div>

      <div className="form-footer">
        {editing ? (
          <>
            <button type="button" className="btn-cancel" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="btn-submit" disabled={loading || !hasChanges || !!nameError}>
              {loading ? "Saving..." : "Save"}
            </button>
          </>
        ) : (
          <div style={{ display: "flex", gap: "8px", width: "100%" }}>
            {onDelete && isSuperAdmin && (
              <button
                type="button"
                className="btn-delete"
                onClick={onDelete}
                disabled={loading}
              >
                Delete
              </button>
            )}
              {record && (
              <button
                type="button"
                className="btn-cancel"
                style={{ display: "flex", alignItems: "center", padding: "0.5rem" }}
                onClick={() => {
                  const typeLabel = (record.typeOption?.label ?? record.type).toUpperCase();
                  const latParts = [];
                  if (record.longitude) latParts.push(`lng-${record.longitude}`);
                  if (record.latitude) latParts.push(`lat-${record.latitude}`);
                  const latLngLine = latParts.length > 0 ? latParts.join("  ") : null;
                  const text = [
                    typeLabel,
                    '',
                    record.client || null,
                    record.contact_number || null,
                    record.address || null,
                    record.jobDetail?.barangay_city || null,
                    latLngLine,
                    record.concern || null,
                  ].filter(line => line !== null).join("\n");
                  try {
                    const ta = document.createElement("textarea");
                    ta.value = text;
                    ta.style.position = "fixed";
                    ta.style.opacity = "0";
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand("copy");
                    document.body.removeChild(ta);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 4000);
                    addToast("Record info copied to clipboard", "success");
                  } catch {
                    addToast("Failed to copy to clipboard", "error");
                  }
                }}
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
              </button>
            )}
            <div style={{ display: "flex", gap: "8px", marginLeft: "auto" }}>
              <button type="button" className="btn-cancel" onClick={onCancel}>
                Close
              </button>
              <button
                type="button"
                className="btn-submit"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onEdit?.();
                }}
              >
                Edit
              </button>
            </div>
          </div>
        )}
      </div>
    </form>
  );
}
