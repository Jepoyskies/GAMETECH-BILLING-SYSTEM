import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Contact } from "lucide-react";
import { useCustomers } from "../hooks/useCustomers";
import { useToast } from "../context/ToastContext";
import api from "../lib/api";
import DataTable from "../components/DataTable";
import SearchFilterInput from "../components/filters/SearchFilterInput";
import LocationField from "../components/map/LocationField";
import BarangayCityAutocomplete from "../components/BarangayCityAutocomplete";
import type { Customer } from "../lib/types";
import "../styles/ListPage.css";

const columns = [
  {
    key: "id",
    header: "ID",
    width: "49px",
    render: (row: Customer) => (
      <span className="row-badge badge-gray">
        {row.id}
      </span>
    ),
  },
  { key: "name", header: "Name", width: "160px" },
  { key: "account_number", header: "Account #", width: "120px" },
  { key: "email", header: "Email", width: "180px" },
  { key: "address", header: "Address", width: "200px" },
  { key: "barangay_city", header: "Barangay/City", width: "130px" },
  { key: "contact_number", header: "Contact", width: "140px" },
];

export default function Customers() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<"name_asc" | "created_desc">("created_desc");

  const { addToast } = useToast();

  const { data, pagination, loading, error, createCustomer } = useCustomers({
    search: search || undefined,
    sort,
    page,
    limit: 100,
  });

  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [accountNumberError, setAccountNumberError] = useState("");
  const [nameError, setNameError] = useState("");
  const [form, setForm] = useState<{
    name: string;
    address: string;
    contact_number: string;
    account_number: string;
    email: string;
    barangay_city: string;
    latitude: number | null;
    longitude: number | null;
  }>({ name: "", address: "", contact_number: "", account_number: "", email: "", barangay_city: "", latitude: null, longitude: null });

  const closeForm = () => {
    setShowForm(false);
    setForm({ name: "", address: "", contact_number: "", account_number: "", email: "", barangay_city: "", latitude: null, longitude: null });
    setAccountNumberError("");
    setNameError("");
  };

  const checkAccountNumber = useCallback(async (value: string) => {
    if (!value.trim()) {
      setAccountNumberError("");
      return;
    }
    try {
      const res = await api.get(`/customers/check-account?account_number=${encodeURIComponent(value.trim())}`);
      if (res.data.data.exists) {
        setAccountNumberError("Account number already exists");
      } else {
        setAccountNumberError("");
      }
    } catch {
      setAccountNumberError("");
    }
  }, []);

  const checkName = useCallback(async (value: string) => {
    if (!value.trim()) {
      setNameError("");
      return;
    }
    try {
      const res = await api.get(`/customers/check-name?name=${encodeURIComponent(value.trim())}`);
      if (res.data.data.exists) {
        setNameError("Customer name already exists");
      } else {
        setNameError("");
      }
    } catch {
      setNameError("");
    }
  }, []);

  useEffect(() => {
    if (error) addToast(error, "error");
  }, [error]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.address.trim() || !form.contact_number.trim()) {
      addToast("All fields are required", "error");
      return;
    }
    if (accountNumberError || nameError) {
      addToast("Please fix the errors before saving", "error");
      return;
    }
    try {
      setSaving(true);
      const created = await createCustomer({
        name: form.name.trim(),
        address: form.address.trim(),
        contact_number: form.contact_number.trim(),
        account_number: form.account_number.trim() || null,
        email: form.email.trim() || null,
        barangay_city: form.barangay_city.trim() || null,
        latitude: form.latitude,
        longitude: form.longitude,
      });
      closeForm();
      navigate(`/customers/${created.id}`);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to create customer", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="list-page">
      <div className="list-header">
        <h1><Contact size={24} /> Customers</h1>
        <button className="btn-primary" onClick={() => setShowForm(true)}>
          + New Customer
        </button>
      </div>

      <div className="filters">
        <div className="filters-right" style={{ justifyContent: "space-between", width: "100%" }}>
          <SearchFilterInput
            value={search}
            placeholder="Search name, contact, acc #, or brg / city"
            onChange={(v) => {
              setSearch(v ?? "");
              setPage(1);
            }}
          />

          <div className="tab-toggle" style={{ marginBottom: 0, marginLeft: "auto" }}>
            <button
              type="button"
              className={sort === "name_asc" ? "active" : ""}
              onClick={() => {
                setSort("name_asc");
                setPage(1);
              }}
            >
              A-Z
            </button>
            <button
              type="button"
              className={sort === "created_desc" ? "active" : ""}
              onClick={() => {
                setSort("created_desc");
                setPage(1);
              }}
            >
              Newest
            </button>
          </div>
        </div>
      </div>

      <DataTable
        data={data}
        columns={columns}
        loading={loading}
        onRowClick={(row: Customer) => navigate(`/customers/${row.id}`)}
        getKey={(row) => row.id}
        fixedLayout
      />

      {pagination && pagination.total_pages > 1 && (
        <div className="pagination">
          <button disabled={pagination.page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </button>
          <span>
            Page {pagination.page} of {pagination.total_pages}
          </span>
          <button
            disabled={pagination.page >= pagination.total_pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}

      {showForm && (
        <div className="modal-overlay">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <form className="form-modal" onSubmit={handleCreate}>
              <div className="form-header">
                <h2>New Customer</h2>
              </div>
              <div className="form-body">
                <div className="form-row">
                  <label>Name</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => {
                      setForm((f) => ({ ...f, name: e.target.value }));
                      setNameError("");
                    }}
                    onBlur={() => checkName(form.name)}
                    className={nameError ? "field-error" : ""}
                    autoFocus
                    required
                  />
                  {nameError && (
                    <span className="form-field-error">{nameError}</span>
                  )}
                </div>
                <div className="form-row">
                  <label>Address</label>
                  <LocationField
                    latitude={form.latitude}
                    longitude={form.longitude}
                    address={form.address}
                    required
                    onChange={(loc) =>
                      setForm((f) => ({
                        ...f,
                        latitude: loc?.latitude ?? null,
                        longitude: loc?.longitude ?? null,
                      }))
                    }
                    onAddressChange={(address) => setForm((f) => ({ ...f, address }))}
                  />
                </div>
                <div className="form-row">
                  <label>Barangay/City</label>
                  <BarangayCityAutocomplete
                    value={form.barangay_city}
                    onChange={(v) => setForm((f) => ({ ...f, barangay_city: v }))}
                  />
                </div>
                <div className="form-row">
                  <label>Contact Number</label>
                  <input
                    type="text"
                    value={form.contact_number}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, contact_number: e.target.value }))
                    }
                    required
                  />
                </div>
                <div className="form-row">
                  <label>Account Number</label>
                  <input
                    type="text"
                    value={form.account_number}
                    onChange={(e) => {
                      setForm((f) => ({ ...f, account_number: e.target.value }));
                      setAccountNumberError("");
                    }}
                    onBlur={() => checkAccountNumber(form.account_number)}
                  />
                  {accountNumberError && (
                    <span className="form-field-error">{accountNumberError}</span>
                  )}
                </div>
                <div className="form-row">
                  <label>Email</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  />
                </div>
              </div>
              <div className="form-footer">
                <button type="button" className="btn-cancel" onClick={closeForm}>
                  Cancel
                </button>
                <button type="submit" className="btn-submit" disabled={saving || !!nameError}>
                  {saving ? "Saving..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
