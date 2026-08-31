import { useState, useEffect, useRef } from "react";
import { useCSR } from "../hooks/useCSR";
import { useConfigOptions } from "../hooks/useConfigOptions";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import type { Dispatch, CustomerSuggestion } from "../lib/types";
import { SOURCE_TABS } from "../lib/constants";
import api from "../lib/api";
import ClientAutocomplete from "./ClientAutocomplete";
import LocationField from "./map/LocationField";
import TechnicianTeamSelector from "./TechnicianTeamSelector";
import BarangayCityAutocomplete from "./BarangayCityAutocomplete";
import "../styles/Forms.css";

interface DispatchFormProps {
  dispatch: Dispatch;
  onSubmit: (data: DispatchFormData) => void;
  onCancel: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  loading?: boolean;
  readOnly?: boolean;
}

export interface DispatchFormData {
  date: string;
  time: string;
  client: string;
  address: string;
  contact_number: string;
  concern: string;
  sales_agent: string;
  csr: number;
  chat_type_id: number;
  type_id: number;
  status_id: number;
  remarks: string;
  time_start: string;
  time_accomplish: string;
  done_at: string;
  source_tab: string;
  ticket_number: string;
  actions_taken: string;
  teams: number[];
  customer_id?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  jobDetail?: {
    schedule_date?: string | null;
    schedule_time?: string | null;
    barangay_city?: string | null;
    account_no?: string | null;
    job_order?: string | null;
    email_address?: string | null;
    nap_port?: string | null;
    cable_length?: string | null;
    nap_reading?: string | null;
    pole_number?: string | null;
    plan_package?: string | null;
    ont_modem_sn?: string | null;
    signal_level?: string | null;
    facility?: string | null;
    house_reading?: string | null;
    special_instruction?: string | null;
    technician_remarks?: string | null;
    acknowledged_by?: string | null;
  };
}

function toLocalDatetime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function toLocalDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function toLocalTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function getCurrentDate(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function getCurrentTime(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

export default function DispatchForm({ 
  dispatch, 
  onSubmit, 
  onCancel, 
  onEdit,
  onDelete,
  loading,
  readOnly = false 
}: DispatchFormProps) {
  const { addToast } = useToast();
  const { isSuperAdmin } = useAuth();
  const { data: csrs } = useCSR();
  const statusOptions = useConfigOptions("STATUS", "DISPATCH", true);
  const typeOptions = useConfigOptions("TYPE", "DISPATCH", true);
  const chatTypeOptions = useConfigOptions("CHAT_TYPE", "DISPATCH", true);

  const [editing, setEditing] = useState(!readOnly);

  useEffect(() => {
    setEditing(!readOnly);
  }, [readOnly]);

  const [customerId, setCustomerId] = useState<number | null>(dispatch.customer_id ?? null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [nameError, setNameError] = useState("");

  const jd = dispatch.monitoring?.jobDetail;

  const [form, setForm] = useState<DispatchFormData>({
    date: dispatch.date ? toLocalDate(dispatch.date) : getCurrentDate(),
    time: dispatch.date ? toLocalTime(dispatch.date) : getCurrentTime(),
    client: dispatch.client || "",
    address: dispatch.address || "",
    contact_number: dispatch.contact_number || "",
    concern: dispatch.concern || "",
    sales_agent: dispatch.sales_agent || "",
    csr: dispatch.csr?.id || 0,
    chat_type_id: dispatch.chatTypeOption?.id ?? 0,
    type_id: dispatch.typeOption?.id ?? 0,
    status_id: dispatch.statusOption?.id ?? 0,
    remarks: dispatch.remarks || "",
    time_start: toLocalDatetime(dispatch.time_start),
    time_accomplish: toLocalDatetime(dispatch.time_accomplish),
    done_at: toLocalDatetime(dispatch.done_at),
    source_tab: dispatch.source_tab || "INTERNET_INSTALL",
    ticket_number: dispatch.ticket_number || "",
    actions_taken: dispatch.actions_taken || "",
    teams: dispatch.teams?.map((t) => t.technician.id) || [],
    latitude: dispatch.latitude ?? null,
    longitude: dispatch.longitude ?? null,
    jobDetail: {
      schedule_date: toLocalDate(jd?.schedule_date) || null,
      schedule_time: jd?.schedule_time ?? null,
      barangay_city: jd?.barangay_city ?? null,
      account_no: jd?.account_no ?? null,
      job_order: jd?.job_order ?? null,
      email_address: jd?.email_address ?? null,
      nap_port: jd?.nap_port ?? null,
      cable_length: jd?.cable_length ?? null,
      nap_reading: jd?.nap_reading ?? null,
      pole_number: jd?.pole_number ?? null,
      plan_package: jd?.plan_package ?? null,
      ont_modem_sn: jd?.ont_modem_sn ?? null,
      signal_level: jd?.signal_level ?? null,
      facility: jd?.facility ?? null,
      house_reading: jd?.house_reading ?? null,
      special_instruction: jd?.special_instruction ?? null,
      technician_remarks: jd?.technician_remarks ?? null,
      acknowledged_by: jd?.acknowledged_by ?? null,
    },
  });

  const initialFormRef = useRef(JSON.stringify(form));

  useEffect(() => {
    initialFormRef.current = JSON.stringify(form);
  }, [readOnly]);

  const hasChanges = JSON.stringify(form) !== initialFormRef.current;

  useEffect(() => {
    if (!dispatch.id && form.status_id === 0 && statusOptions.options.length > 0) {
      const pending = statusOptions.options.find(
        (opt) => opt.label === "Pending"
      );
      if (pending) {
        setForm((f) => ({ ...f, status_id: pending.id }));
      }
    }
  }, [statusOptions.options, dispatch.id, form.status_id]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Record<string, string> = {};

    if (!form.date) newErrors.date = "Date is required";
    if (!form.client) newErrors.client = "Client is required";
    if (!form.address) newErrors.address = "Address is required";
    if (!form.contact_number) newErrors.contact_number = "Contact number is required";
    if (!form.csr) newErrors.csr = "CSR is required";
    if (!form.type_id) newErrors.type_id = "Type is required";
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

    const filteredJobDetail: Record<string, string | null> = {};
    if (form.jobDetail) {
      for (const [key, value] of Object.entries(form.jobDetail)) {
        filteredJobDetail[key] = value || null;
      }
    }

    const payload: DispatchFormData = {
      ...form,
      teams: form.teams.filter((t) => t !== 0),
      customer_id: customerId,
      jobDetail: filteredJobDetail,
    };

    setErrors({});
    onSubmit(payload);
  };

  const updateField = (field: keyof DispatchFormData, value: string | number) => {
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

  const toggleTeam = (techId: number) => {
    setForm((f): DispatchFormData => {
      const teams = f.teams.includes(techId)
        ? f.teams.filter((t) => t !== techId)
        : [...f.teams, techId];
      return { ...f, teams };
    });
  };

  const toggleTeamMany = (techIds: number[], select: boolean) => {
    setForm((f): DispatchFormData => {
      const set = new Set(f.teams);
      techIds.forEach((id) => (select ? set.add(id) : set.delete(id)));
      return { ...f, teams: [...set] };
    });
  };

  const isConcernsTab = form.source_tab === "CLIENT_CONCERNS";
  const isInstallRepair = form.source_tab === "INTERNET_INSTALL" || form.source_tab === "CIGNAL_PLAY";
  const disabled = !editing;

  const updateJobDetail = (field: string, value: string | null) => {
    setForm((f) => ({
      ...f,
      jobDetail: { ...f.jobDetail, [field]: value || null },
    }));
  };

  return (
    <form className="form-modal" onSubmit={handleSubmit}>
      <div className="form-header">
        <h2>{editing ? "Edit Dispatch" : `Dispatch #${dispatch.id}`}</h2>
      </div>

      <div className="form-body">

        {/* ── Job Info ── */}
        <div className="section-divider">
          <span className="section-divider-label">Job Info</span>
        </div>
        <div className="form-row-group">
          <div className="form-row">
            <label>Date Created</label>
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
                setErrors((prev) => ({ ...prev, date: "" }));
              }}
              disabled={disabled}

              required
            />
            {errors.date && <div className="form-field-error">{errors.date}</div>}
          </div>
          <div className="form-row">
            <label>Date Completed</label>
            <input
              type="datetime-local"
              value={form.done_at}
              onChange={(e) => {
                if (e.target.value) updateField("done_at", e.target.value);
              }}
              disabled={disabled}

            />
          </div>
        </div>
        <div className="form-row-group">
          <div className="form-row">
            <label>Type</label>
            <select value={form.type_id} onChange={(e) => { updateField("type_id", Number(e.target.value)); setErrors((prev) => ({ ...prev, type_id: "" })); }} disabled={disabled || typeOptions.loading} required>
              <option value={0}>Select type</option>
              {typeOptions.options.filter((o) => o.active).map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
            {errors.type_id && <div className="form-field-error">{errors.type_id}</div>}
          </div>
          <div className="form-row">
            <label>Chat Type</label>
            <select value={form.chat_type_id} onChange={(e) => updateField("chat_type_id", Number(e.target.value))} disabled={disabled || chatTypeOptions.loading} required>
              <option value={0}>Select chat type</option>
              {chatTypeOptions.options.filter((o) => o.active).map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="form-row-group">
          <div className="form-row">
            <label>Status</label>
            <select value={form.status_id} onChange={(e) => { updateField("status_id", Number(e.target.value)); setErrors((prev) => ({ ...prev, status_id: "" })); }} disabled={disabled || statusOptions.loading} required>
              <option value={0}>Select status</option>
              {statusOptions.options.filter((o) => o.active).map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
            {errors.status_id && <div className="form-field-error">{errors.status_id}</div>}
          </div>
          <div className="form-row">
            <label>Source</label>
            <input
              type="text"
              value={SOURCE_TABS.find((s) => s.value === form.source_tab)?.label || form.source_tab}
              disabled
            />
          </div>
        </div>
        <div className="form-row-group">
          <div className="form-row">
            <label>CSR</label>
            <select
              value={form.csr}
              onChange={(e) => { updateField("csr", Number(e.target.value)); setErrors((prev) => ({ ...prev, csr: "" })); }}
              disabled={disabled}
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
          <div className="form-row">
            <label>Sales Agent</label>
            <input
              type="text"
              value={form.sales_agent}
              onChange={(e) => updateField("sales_agent", e.target.value)}
              disabled={disabled}
            />
          </div>
        </div>

        {/* ── Subscriber Info ── */}
        <div className="section-divider">
          <span className="section-divider-label">Subscriber Info</span>
        </div>
        <div className="form-row-group">
          <div className="form-row">
            <label>Client</label>
            <ClientAutocomplete
              value={form.client}
              onChange={(value) => { updateField("client", value); setErrors((prev) => ({ ...prev, client: "" })); setNameError(""); }}
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
            <label>Contact Number</label>
            <input
              type="text"
              value={form.contact_number}
              onChange={(e) => { updateField("contact_number", e.target.value); setErrors((prev) => ({ ...prev, contact_number: "" })); }}
              disabled={disabled}

              required
            />
            {errors.contact_number && <div className="form-field-error">{errors.contact_number}</div>}
          </div>
        </div>
        {(isInstallRepair || isConcernsTab) && (
          <div className="form-row-group">
            <div className="form-row">
              <label>Account No.</label>
              <input type="text" value={form.jobDetail?.account_no || ""} onChange={(e) => updateJobDetail("account_no", e.target.value)} disabled={disabled} />
            </div>
            <div className="form-row">
              <label>Email Address</label>
              <input type="email" value={form.jobDetail?.email_address || ""} onChange={(e) => updateJobDetail("email_address", e.target.value)} disabled={disabled} />
            </div>
          </div>
        )}

        {/* ── Location ── */}
        <div className="section-divider">
          <span className="section-divider-label">Location</span>
        </div>
        <div className="form-row">
          <label>Address</label>
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
            onAddressChange={(address) => { updateField("address", address); setErrors((prev) => ({ ...prev, address: "" })); }}
          />
        </div>
        {(isInstallRepair || isConcernsTab) && (
          <div className="form-row">
            <label>Barangay/City</label>
            <BarangayCityAutocomplete
              value={form.jobDetail?.barangay_city || ""}
              onChange={(v) => updateJobDetail("barangay_city", v)}
              disabled={disabled}
            />
          </div>
        )}

        {/* ── Issue ── */}
        <div className="section-divider">
          <span className="section-divider-label">Issue</span>
        </div>
        <div className="form-row">
          <label>Concern</label>
          <textarea
            value={form.concern}
            onChange={(e) => updateField("concern", e.target.value)}
            disabled={disabled}

          />
        </div>

        {/* ── Scheduling ── */}
        {(isInstallRepair || isConcernsTab) && (
          <>
            <div className="section-divider">
              <span className="section-divider-label">Scheduling</span>
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>Schedule Date</label>
                <input type="date" value={form.jobDetail?.schedule_date || ""} onChange={(e) => updateJobDetail("schedule_date", e.target.value)} disabled={disabled} />
              </div>
              <div className="form-row">
                <label>Schedule Time</label>
                <div className="time-input-wrapper">
                  <input type="time" value={form.jobDetail?.schedule_time || ""} onChange={(e) => updateJobDetail("schedule_time", e.target.value)} disabled={disabled} />
                  <button type="button" className="time-clear-btn" onClick={() => updateJobDetail("schedule_time", "")} disabled={disabled || !form.jobDetail?.schedule_time} title="Clear time">
                    ×
                  </button>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── Work Timeline ── */}
        <div className="section-divider">
          <span className="section-divider-label">Work Timeline</span>
        </div>
        <div className="form-row-group">
          <div className="form-row">
            <label>Service Start</label>
            <input
              type="datetime-local"
              value={form.time_start}
              onChange={(e) => updateField("time_start", e.target.value)}
              disabled={disabled}

            />
          </div>
          <div className="form-row">
            <label>Service End</label>
            <input
              type="datetime-local"
              value={form.time_accomplish}
              onChange={(e) => updateField("time_accomplish", e.target.value)}
              disabled={disabled}

            />
          </div>
        </div>

        {/* ── Service Details ── */}
        {(isInstallRepair || isConcernsTab) && (
          <>
            <div className="section-divider">
              <span className="section-divider-label">Service Details</span>
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>Job Order No.</label>
                <input type="text" value={form.jobDetail?.job_order || ""} onChange={(e) => updateJobDetail("job_order", e.target.value)} disabled={disabled} />
              </div>
              <div className="form-row">
                <label>NAP/Port</label>
                <input type="text" value={form.jobDetail?.nap_port || ""} onChange={(e) => updateJobDetail("nap_port", e.target.value)} disabled={disabled} />
              </div>
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>NAP Reading</label>
                <input type="text" value={form.jobDetail?.nap_reading || ""} onChange={(e) => updateJobDetail("nap_reading", e.target.value)} disabled={disabled} />
              </div>
              <div className="form-row">
                <label>House Reading</label>
                <input type="text" value={form.jobDetail?.house_reading || ""} onChange={(e) => updateJobDetail("house_reading", e.target.value)} disabled={disabled} />
              </div>
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>Pole Number</label>
                <input type="text" value={form.jobDetail?.pole_number || ""} onChange={(e) => updateJobDetail("pole_number", e.target.value)} disabled={disabled} />
              </div>
              <div className="form-row">
                <label>Cable Length Used</label>
                <input type="text" value={form.jobDetail?.cable_length || ""} onChange={(e) => updateJobDetail("cable_length", e.target.value)} disabled={disabled} />
              </div>
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>Signal Level</label>
                <input type="text" value={form.jobDetail?.signal_level || ""} onChange={(e) => updateJobDetail("signal_level", e.target.value)} disabled={disabled} />
              </div>
              <div className="form-row">
                <label>Facility</label>
                <input type="text" value={form.jobDetail?.facility || ""} onChange={(e) => updateJobDetail("facility", e.target.value)} disabled={disabled} />
              </div>
            </div>
            <div className="form-row">
              <label>ONT/Modem SN</label>
              <input type="text" value={form.jobDetail?.ont_modem_sn || ""} onChange={(e) => updateJobDetail("ont_modem_sn", e.target.value)} disabled={disabled} />
            </div>
            {(form.source_tab === "INTERNET_INSTALL" || form.source_tab === "CIGNAL_PLAY") && (
              <div className="form-row">
                <label>Plan/Package (Installation Only)</label>
                <input type="text" value={form.jobDetail?.plan_package || ""} onChange={(e) => updateJobDetail("plan_package", e.target.value)} disabled={disabled} />
              </div>
            )}
          </>
        )}

        {/* ── Sign Off ── */}
        <div className="section-divider">
          <span className="section-divider-label">Sign Off</span>
        </div>
        {(isInstallRepair || isConcernsTab) && (
          <>
            <div className="form-row">
              <label>Special Instruction</label>
              <textarea value={form.jobDetail?.special_instruction || ""} onChange={(e) => updateJobDetail("special_instruction", e.target.value)} disabled={disabled} rows={2} />
            </div>
            <div className="form-row">
              <label>Technician Remarks</label>
              <textarea value={form.jobDetail?.technician_remarks || ""} onChange={(e) => updateJobDetail("technician_remarks", e.target.value)} disabled={disabled} rows={2} />
            </div>
            <div className="form-row">
              <label>Remarks</label>
              <textarea
                value={form.remarks}
                onChange={(e) => updateField("remarks", e.target.value)}
                disabled={disabled}
              />
            </div>
            <div className="form-row">
              <label>Acknowledged By</label>
              <input type="text" value={form.jobDetail?.acknowledged_by || ""} onChange={(e) => updateJobDetail("acknowledged_by", e.target.value)} disabled={disabled} />
            </div>
          </>
        )}
        {!isInstallRepair && !isConcernsTab && (
          <div className="form-row">
            <label>Remarks</label>
            <textarea
              value={form.remarks}
              onChange={(e) => updateField("remarks", e.target.value)}
              disabled={disabled}
            />
          </div>
        )}

        {/* ── Concerns-only fields ── */}
        {isConcernsTab && (
          <>
            <div className="form-row">
              <label>Actions Taken</label>
              <textarea
                value={form.actions_taken}
                onChange={(e) => updateField("actions_taken", e.target.value)}
                disabled={disabled}

              />
            </div>
            <div className="form-row">
              <label>Ticket No.</label>
              <input
                type="text"
                value={form.ticket_number}
                onChange={(e) => updateField("ticket_number", e.target.value)}
                disabled={disabled}

              />
            </div>
          </>
        )}

        {/* ── Technicians ── */}
        <div className="section-divider">
          <span className="section-divider-label">Technicians</span>
        </div>
        <div className="form-row">
          <TechnicianTeamSelector
            selected={form.teams}
            onToggle={toggleTeam}
            onToggleMany={toggleTeamMany}
            disabled={disabled}
            idPrefix="dispatch-form-tech"
          />
        </div>
      </div>

      <div className="form-footer">
        {editing ? (
          <>
            <button type="button" className="btn-cancel" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="btn-submit" disabled={loading || !hasChanges}>
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
                  setEditing(true);
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
