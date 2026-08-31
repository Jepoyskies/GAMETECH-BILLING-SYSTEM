import { useEffect, useState, useCallback } from "react";
import { Contact, Pen, Trash2 } from "lucide-react";
import { useParams, useNavigate } from "react-router-dom";
import { useCustomerDetail } from "../hooks/useCustomers";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import DataTable from "../components/DataTable";
import LocationField from "../components/map/LocationField";
import BarangayCityAutocomplete from "../components/BarangayCityAutocomplete";
import type { CustomerJob } from "../lib/types";
import "../styles/ListPage.css";
import "../styles/CustomerDashboard.css";

const MODULE_LABELS: Record<string, string> = {
  DISPATCH_LOG: "Dispatch Log",
  INTERNET_INSTALL: "Internet Install",
  CIGNAL_PLAY: "Cignal Play",
  CLIENT_CONCERNS: "Client Concerns",
};

const TYPE_LABELS: Record<string, string> = {
  UNASSIGNED: "Unassigned",
};

const jobColumns = [
  {
    key: "date",
    header: "Date Created",
    width: "140px",
    render: (row: CustomerJob) =>
      new Date(row.date).toLocaleString(undefined, {
        year: "numeric",
        month: "numeric",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }),
  },
  {
    key: "done_at",
    header: "Date Completed",
    width: "140px",
    render: (row: CustomerJob) =>
      row.done_at
        ? new Date(row.done_at).toLocaleString(undefined, {
            year: "numeric",
            month: "numeric",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
          })
        : "-",
  },
  {
    key: "turnaround",
    header: "Turnaround",
    width: "100px",
    render: (row: CustomerJob) => {
      if (!row.done_at) return "-";
      const doneAt = new Date(row.done_at).getTime();
      const created = new Date(row.date).getTime();
      const diffMinutes = Math.round((doneAt - created) / 60000);
      if (diffMinutes < 0) return "-";
      const days = Math.floor(diffMinutes / (60 * 24));
      const hours = Math.floor((diffMinutes % (60 * 24)) / 60);
      const minutes = diffMinutes % 60;
      const parts = [];
      if (days > 0) parts.push(`${days}d`);
      if (hours > 0) parts.push(`${hours}h`);
      if (minutes > 0 || parts.length === 0) parts.push(`${minutes}m`);
      return parts.join(" ");
    },
  },
  {
    key: "module",
    header: "Module",
    width: "150px",
    render: (row: CustomerJob) => MODULE_LABELS[row.module] ?? row.module,
  },
  {
    key: "type",
    header: "Type",
    width: "130px",
    render: (row: CustomerJob) => (row.type ? TYPE_LABELS[row.type] ?? row.type : "Unassigned"),
  },
  {
    key: "status",
    header: "Status",
    width: "130px",
    render: (row: CustomerJob) => (
      <>
        {row.status}
        {row.source === "MONITORING" && row.time_start && (
          <span className="status-ongoing"> / Ongoing</span>
        )}
      </>
    ),
  },
  { key: "concern", header: "Concern", width: "260px" },
  {
    key: "ticket_number",
    header: "Ticket No.",
    width: "130px",
    render: (row: CustomerJob) => row.ticket_number || "-",
  },
];

export default function CustomerDashboard() {
  const { id } = useParams<{ id: string }>();
  const customerId = Number(id);
  const navigate = useNavigate();

  const [jobsPage, setJobsPage] = useState(1);
  const { customer, stats, jobs, jobsPagination, loading, error, updateCustomer, deleteCustomer } =
    useCustomerDetail(customerId, jobsPage);

  const { addToast } = useToast();
  const { isSuperAdmin } = useAuth();

  useEffect(() => {
    if (error && !customer) addToast(error, "error");
  }, [error, customer]);

  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState<{
    name: string;
    address: string;
    contact_number: string;
    account_number: string;
    email: string;
    barangay_city: string;
    latitude: number | null;
    longitude: number | null;
  }>({ name: "", address: "", contact_number: "", account_number: "", email: "", barangay_city: "", latitude: null, longitude: null });
  const [saving, setSaving] = useState(false);
  const [accountNumberError, setAccountNumberError] = useState("");
  const [nameError, setNameError] = useState("");

  const [showDelete, setShowDelete] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);

  const openEdit = () => {
    if (!customer) return;
    setEditForm({
      name: customer.name,
      address: customer.address,
      contact_number: customer.contact_number,
      account_number: customer.account_number ?? "",
      email: customer.email ?? "",
      barangay_city: customer.barangay_city ?? "",
      latitude: customer.latitude ?? null,
      longitude: customer.longitude ?? null,
    });
    setAccountNumberError("");
    setNameError("");
    setShowEdit(true);
  };

  const checkAccountNumber = useCallback(async (value: string) => {
    if (!value.trim()) {
      setAccountNumberError("");
      return;
    }
    try {
      const res = await api.get(`/customers/check-account?account_number=${encodeURIComponent(value.trim())}&exclude_id=${customerId}`);
      if (res.data.data.exists) {
        setAccountNumberError("Account number already exists");
      } else {
        setAccountNumberError("");
      }
    } catch {
      setAccountNumberError("");
    }
  }, [customerId]);

  const checkName = useCallback(async (value: string) => {
    if (!value.trim()) {
      setNameError("");
      return;
    }
    try {
      const res = await api.get(`/customers/check-name?name=${encodeURIComponent(value.trim())}&exclude_id=${customerId}`);
      if (res.data.data.exists) {
        setNameError("Customer name already exists");
      } else {
        setNameError("");
      }
    } catch {
      setNameError("");
    }
  }, [customerId]);

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (accountNumberError || nameError) {
      addToast("Please fix the errors before saving", "error");
      return;
    }
    try {
      setSaving(true);
      await updateCustomer({
        name: editForm.name.trim(),
        address: editForm.address.trim(),
        contact_number: editForm.contact_number.trim(),
        account_number: editForm.account_number.trim() || null,
        email: editForm.email.trim() || null,
        barangay_city: editForm.barangay_city.trim() || null,
        latitude: editForm.latitude,
        longitude: editForm.longitude,
      });
      addToast("Customer updated successfully", "success");
      setShowEdit(false);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to update", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setDeleting(true);
      await deleteCustomer(deleteConfirm.trim());
      addToast("Customer deleted successfully", "success");
      navigate("/customers");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to delete", "error");
    } finally {
      setDeleting(false);
    }
  };

  if (loading && !customer) {
    return <div className="list-page"><p>Loading…</p></div>;
  }

  if (error && !customer) {
    return (
      <div className="list-page">
        <p>Could not load customer details.</p>
        <button className="btn-cancel" onClick={() => navigate("/customers")}>
          ← Back to Customers
        </button>
      </div>
    );
  }

  if (!customer) return null;

  return (
    <div className="list-page">
      <div className="list-header">
        <div>
          <button className="link-back" onClick={() => navigate("/customers")}>
            ← Back
          </button>
          <h1><Contact size={24} /> {customer.name}</h1>
        </div>
        <div className="row-actions">
          <button className="btn-edit" onClick={openEdit}>
            <Pen size={16} /> Edit Info
          </button>
          {isSuperAdmin && (
            <button className="btn-delete" onClick={() => setShowDelete(true)}>
              <Trash2 size={16} /> Delete
            </button>
          )}
        </div>
      </div>

      {/* Master info */}
      <div className="customer-master">
        <div className="master-address">
          <span className="master-label">Address</span>
          <span className="master-value">{customer.address}</span>
          <LocationField
            latitude={customer.latitude ?? null}
            longitude={customer.longitude ?? null}
            disabled
          />
        </div>
        <div className="master-details">
          <div className="master-field">
            <span className="master-label">Contact Number</span>
            <span className="master-value">{customer.contact_number}</span>
          </div>
          <div className="master-field">
            <span className="master-label">Account Number</span>
            <span className="master-value">{customer.account_number || "-"}</span>
          </div>
          <div className="master-field">
            <span className="master-label">Email</span>
            <span className="master-value">{customer.email || "-"}</span>
          </div>
          <div className="master-field">
            <span className="master-label">Barangay/City</span>
            <span className="master-value">{customer.barangay_city || "-"}</span>
          </div>
        </div>
      </div>

      {/* Stats summary */}
      {stats && (
        <div className="stats-section">
          <div className="stat-cards">
            <div className="stat-card highlight">
              <span className="stat-number">{stats.total_jobs}</span>
              <span className="stat-label">Total Jobs</span>
            </div>
            {Object.entries(stats.by_status)
              .filter(([, count]) => count > 0)
              .map(([status, count]) => (
                <div className="stat-card" key={status}>
                  <span className="stat-number">{count}</span>
                  <span className="stat-label">{status}</span>
                </div>
              ))}
          </div>

          <div className="stats-breakdown">
            <h3>By Type</h3>
            <div className="breakdown-chips">
              {Object.keys(stats.by_type).length === 0 && (
                <span className="muted">No jobs yet</span>
              )}
              {Object.entries(stats.by_type).map(([type, count]) => (
                <span className="breakdown-chip" key={type}>
                  {TYPE_LABELS[type] ?? type}: <strong>{count}</strong>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Job history */}
      <h3 className="section-title">Job History</h3>
      <DataTable
        data={jobs}
        columns={jobColumns}
        loading={loading}
        getKey={(row: CustomerJob) => `${row.source}-${row.id}`}
        fixedLayout
      />

      {jobsPagination && jobsPagination.total_pages > 1 && (
        <div className="pagination">
          <button disabled={jobsPagination.page <= 1} onClick={() => setJobsPage((p) => p - 1)}>
            Previous
          </button>
          <span>
            Page {jobsPagination.page} of {jobsPagination.total_pages}
          </span>
          <button
            disabled={jobsPagination.page >= jobsPagination.total_pages}
            onClick={() => setJobsPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}

      {showEdit && (
        <div className="modal-overlay">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <form className="form-modal" onSubmit={handleEditSubmit}>
              <div className="form-header">
                <h2>Edit Customer</h2>
              </div>
              <div className="form-body">
                <div className="form-row">
                  <label>Name</label>
                  <input
                    type="text"
                    value={editForm.name}
                    onChange={(e) => {
                      setEditForm((f) => ({ ...f, name: e.target.value }));
                      setNameError("");
                    }}
                    onBlur={() => checkName(editForm.name)}
                    className={nameError ? "field-error" : ""}
                    required
                  />
                  {nameError && (
                    <span className="form-field-error">{nameError}</span>
                  )}
                </div>
                <div className="form-row">
                  <label>Address</label>
                  <LocationField
                    latitude={editForm.latitude}
                    longitude={editForm.longitude}
                    address={editForm.address}
                    required
                    onChange={(loc) =>
                      setEditForm((f) => ({
                        ...f,
                        latitude: loc?.latitude ?? null,
                        longitude: loc?.longitude ?? null,
                      }))
                    }
                    onAddressChange={(address) => setEditForm((f) => ({ ...f, address }))}
                  />
                </div>
                <div className="form-row">
                  <label>Barangay/City</label>
                  <BarangayCityAutocomplete
                    value={editForm.barangay_city}
                    onChange={(v) => setEditForm((f) => ({ ...f, barangay_city: v }))}
                  />
                </div>
                <div className="form-row">
                  <label>Contact Number</label>
                  <input
                    type="text"
                    value={editForm.contact_number}
                    onChange={(e) =>
                      setEditForm((f) => ({ ...f, contact_number: e.target.value }))
                    }
                    required
                  />
                </div>
                <div className="form-row">
                  <label>Account Number</label>
                  <input
                    type="text"
                    value={editForm.account_number}
                    onChange={(e) => {
                      setEditForm((f) => ({ ...f, account_number: e.target.value }));
                      setAccountNumberError("");
                    }}
                    onBlur={() => checkAccountNumber(editForm.account_number)}
                  />
                  {accountNumberError && (
                    <span className="form-field-error">{accountNumberError}</span>
                  )}
                </div>
                <div className="form-row">
                  <label>Email</label>
                  <input
                    type="email"
                    value={editForm.email}
                    onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                  />
                </div>
              </div>
              <div className="form-footer">
                <button type="button" className="btn-cancel" onClick={() => setShowEdit(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-submit" disabled={saving || !!nameError}>
                  {saving ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showDelete && (
        <div className="modal-overlay">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <form className="form-modal" onSubmit={handleDelete}>
              <div className="form-header">
                <h2>Delete Customer</h2>
              </div>
              <div className="form-body">
                <p className="delete-warning">
                  This removes the master record for <strong>{customer.name}</strong>. Existing job
                  records keep their snapshots.
                </p>
                <div className="form-row">
                  <label>Type the customer name to confirm</label>
                  <input
                    type="text"
                    value={deleteConfirm}
                    onChange={(e) => setDeleteConfirm(e.target.value)}
                    placeholder={customer.name}
                    autoFocus
                  />
                </div>
              </div>
              <div className="form-footer">
                <button type="button" className="btn-cancel" onClick={() => setShowDelete(false)}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-delete-submit"
                  disabled={deleting || deleteConfirm.trim() !== customer.name}
                >
                  {deleting ? "Deleting..." : "Delete Customer"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}