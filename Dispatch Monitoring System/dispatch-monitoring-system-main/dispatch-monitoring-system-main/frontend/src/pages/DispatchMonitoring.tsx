import { useEffect, useState, useCallback } from "react";
import { ClipboardList, FilterX } from "lucide-react";
import { SOURCE_TABS } from "../lib/constants";
import { useDispatches, Dispatch, DispatchFilters } from "../hooks/useDispatches";
import { useCSR } from "../hooks/useCSR";
import { useConfigOptions } from "../hooks/useConfigOptions";
import { useToast } from "../context/ToastContext";
import DataTable from "../components/DataTable";
import DispatchForm, { DispatchFormData } from "../components/DispatchForm";
import DateRangePicker from "../components/filters/DateRangePicker";
import SearchFilterInput from "../components/filters/SearchFilterInput";
import MoreFiltersPopover from "../components/filters/MoreFiltersPopover";
import { appendFilterParams } from "../lib/filterParams";
import ExportMonthDropdown from "../components/filters/ExportMonthDropdown";
import "../styles/ListPage.css";

function toIsoOrNull(value: string): string | null {
  if (!value) return null;
  return new Date(value).toISOString();
}

function formatDuration(minutes: number): string {
  const days = Math.floor(minutes / 1440);
  const hrs = Math.floor((minutes % 1440) / 60);
  const mins = minutes % 60;
  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hrs > 0) parts.push(`${hrs}h`);
  if (mins > 0 || parts.length === 0) parts.push(`${mins}m`);
  return parts.join(" ");
}

const DISPATCH_FILTERS_KEY = "dispatchMonitoringFilters";

const defaultDispatchFilters: DispatchFilters = {
  limit: 150,
  sort_by: "date",
};

function loadDispatchFilters(): DispatchFilters {
  try {
    const stored = localStorage.getItem(DISPATCH_FILTERS_KEY);
    if (stored) return { ...defaultDispatchFilters, ...JSON.parse(stored) };
  } catch { /* ignore */ }
  return { ...defaultDispatchFilters };
}

export default function DispatchMonitoring() {
  const [filters, setFilters] = useState<DispatchFilters>(loadDispatchFilters);
  const [cursorHistory, setCursorHistory] = useState<number[]>([]);
  const [clearKey, setClearKey] = useState(0);

  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formDispatch, setFormDispatch] = useState<Dispatch | null>(null);
  const [formReadOnly, setFormReadOnly] = useState(false);
  const [saving, setSaving] = useState(false);

  const { addToast } = useToast();

  const [deleteDispatchTarget, setDeleteDispatchTarget] = useState<Dispatch | null>(null);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [deleteSaving, setDeleteSaving] = useState(false);

  const { data: csrs } = useCSR();
  const statusOptions = useConfigOptions("STATUS", "DISPATCH", true);
  const typeOptions = useConfigOptions("TYPE", "DISPATCH", true);
  const chatTypeOptions = useConfigOptions("CHAT_TYPE", "DISPATCH", true);
  const { data, pagination, loading, error: fetchError, updateDispatch, deleteDispatch } =
    useDispatches(filters);

  useEffect(() => {
    if (error || fetchError) addToast(error || fetchError!, "error");
  }, [error, fetchError]);

  useEffect(() => {
    const { cursor: _, ...toStore } = filters;
    localStorage.setItem(DISPATCH_FILTERS_KEY, JSON.stringify(toStore));
  }, [filters]);

  const updateFilter = useCallback(
    (patch: Partial<DispatchFilters>) => {
      setFilters((f) => ({ ...f, ...patch, cursor: undefined }));
      setCursorHistory([]);
    },
    []
  );

  const hasActive = [
    filters.date_from, filters.date_to,
    filters.type_id, filters.source_tab,
    filters.csr, filters.chat_type_id, filters.status_id,
    filters.teams, filters.ticket_number, filters.job_details, filters.address,
    filters.client,
    filters.done_from, filters.done_to,
    filters.time_start_from, filters.time_start_to,
  ].some((v) => v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0));

  const clearFilters = () => {
    setFilters({ limit: 150, sort_by: "date" });
    setCursorHistory([]);
    setClearKey((k) => k + 1);
  };

  const handleNext = useCallback(() => {
    if (!pagination?.has_next || pagination.next_cursor === null) return;
    setCursorHistory((prev) => [...prev, filters.cursor ?? 0]);
    setFilters((f) => ({ ...f, cursor: pagination.next_cursor! }));
  }, [pagination, filters.cursor]);

  const handlePrev = useCallback(() => {
    setCursorHistory((prev) => {
      if (prev.length === 0) return prev;
      const newHistory = [...prev];
      const prevCursor = newHistory.pop()!;
      setFilters((f) => ({ ...f, cursor: prevCursor || undefined }));
      return newHistory;
    });
  }, []);

  const handleDelete = (dispatch: Dispatch) => {
    setDeleteDispatchTarget(dispatch);
    setDeleteConfirmName("");
  };

  const handleConfirmDeleteDispatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deleteDispatchTarget) return;
    try {
      setDeleteSaving(true);
      await deleteDispatch(deleteDispatchTarget.id, deleteConfirmName.trim());
      addToast("Dispatch deleted successfully", "success");
      setDeleteDispatchTarget(null);
      setDeleteConfirmName("");
      if (formDispatch?.id === deleteDispatchTarget.id) {
        setShowForm(false);
        setFormDispatch(null);
      }
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to delete", "error");
    } finally {
      setDeleteSaving(false);
    }
  };

  const closeForm = () => {
    setShowForm(false);
    setFormDispatch(null);
    setFormReadOnly(false);
  };

  const handleView = (row: Dispatch) => {
    setFormDispatch(row);
    setFormReadOnly(true);
    setShowForm(true);
    setError(null);
  };

  const handleEdit = () => {
    setFormReadOnly(false);
  };

  const handleSubmit = async (formData: DispatchFormData) => {
    if (!formDispatch) return;
    try {
      setSaving(true);
      setError(null);
      const updated = await updateDispatch(formDispatch.id, {
        ...formData,
        time_start: toIsoOrNull(formData.time_start),
        time_accomplish: toIsoOrNull(formData.time_accomplish),
      });
      setFormDispatch((prev) => prev ? { ...prev, ...updated } : prev);
      setFormReadOnly(true);
      addToast("Dispatch updated successfully", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };


  const columns = [
    { key: "statusOption", header: "Status", width: "130px" },
    {
      key: "date",
      header: "Date Created",
      width: "150px",
      headerClassName: filters.sort_by === "date" ? "th-highlight-dispatch" : undefined,
      render: (row: Dispatch) => new Date(row.date).toLocaleString(undefined, { year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" }),
    },
    {
      key: "done_at",
      header: "Date Completed",
      width: "150px",
      headerClassName: filters.sort_by === "done_at" ? "th-highlight-dispatch" : undefined,
      render: (row: Dispatch) => row.monitoring?.done_at
        ? new Date(row.monitoring.done_at).toLocaleString(undefined, { year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" })
        : "-",
    },
    {
      key: "turnaround",
      header: "Turnaround",
      width: "105px",
      render: (row: Dispatch) => {
        if (!row.monitoring?.done_at) return "-";
        const doneAt = new Date(row.monitoring.done_at).getTime();
        const date = new Date(row.date).getTime();
        const diffMinutes = Math.round((doneAt - date) / 60000);
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
    { key: "client", header: "Client", width: "310px" },
    { key: "concern", header: "Concern", width: "320px" },
    { key: "ticket_number", header: "Ticket No.", width: "150px" },
    { key: "typeOption", header: "Type", width: "160px" },
    { key: "chatTypeOption", header: "Chat Type", width: "125px" },
    { key: "source_tab", header: "Source", width: "160px" },
    {
      key: "time_start",
      header: "Service Start",
      width: "165px",
      render: (row: Dispatch) => row.time_start ? new Date(row.time_start).toLocaleString(undefined, { year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" }) : "-",
    },
    {
      key: "time_accomplish",
      header: "Service End",
      width: "165px",
      render: (row: Dispatch) => row.time_accomplish ? new Date(row.time_accomplish).toLocaleString(undefined, { year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" }) : "-",
    },
    {
      key: "duration",
      header: "Service Duration",
      width: "140px",
      render: (row: Dispatch) => row.duration ? formatDuration(row.duration) : "-",
    },
    {
      key: "teams",
      header: "Team",
      width: "250px",
      render: (row: Dispatch) =>
        row.teams?.map((t) => t.technician.name).join(", ") || "-",
    },
    { key: "csr", header: "CSR", width: "185px", render: (row: Dispatch) => row.csr?.name },
    { key: "sales_agent", header: "Sales Agent", width: "190px" },
    { key: "address", header: "Address", width: "350px" },
    {
      key: "barangay_city",
      header: "Brgy/City",
      width: "250px",
      render: (row: Dispatch) => row.monitoring?.jobDetail?.barangay_city ?? "-",
    },
    { key: "contact_number", header: "Contact", width: "190px" },
    { key: "actions_taken", header: "Actions Taken", width: "250px" },
    { key: "remarks", header: "Remarks", width: "230px" },
  ];

  const exportFilterParams = new URLSearchParams();
  appendFilterParams(exportFilterParams, {
    status_id: filters.status_id,
    type_id: filters.type_id,
    source_tab: filters.source_tab,
    chat_type_id: filters.chat_type_id,
    csr: filters.csr,
    client: filters.client,
    teams: filters.teams,
    ticket_number: filters.ticket_number,
    job_details: filters.job_details,
    address: filters.address,
    done_from: filters.done_from,
    done_to: filters.done_to,
    time_start_from: filters.time_start_from,
    time_start_to: filters.time_start_to,
  });

  return (
    <div className="list-page">
      <div className="list-header">
        <h1><ClipboardList size={24} /> Dispatch Log</h1>
        <div className="list-header-actions">
          <select
            className="sort-select"
            value={filters.sort_by ?? "date"}
            onChange={(e) =>
              updateFilter({ sort_by: e.target.value as "date" | "done_at" })
            }
          >
            <option value="date">Sort: Date Created</option>
            <option value="done_at">Sort: Date Completed</option>
          </select>
          <ExportMonthDropdown
            resourcePath="/dispatches"
            filePrefix="dispatch-log"
            filterParams={exportFilterParams}
          />
        </div>
      </div>

      <div className="filters">
        <div className="filters-left">
          <DateRangePicker
            dateFrom={filters.date_from}
            dateTo={filters.date_to}
            onChange={({ date_from, date_to }) =>
              updateFilter({ date_from, date_to })
            }
          />

          <select
            value={filters.type_id ?? ""}
            onChange={(e) => updateFilter({ type_id: e.target.value ? Number(e.target.value) : undefined })}
          >
            <option value="">All Types</option>
            {typeOptions.options.map((t) => (
              <option key={t.id} value={t.id}>{t.label}</option>
            ))}
          </select>

          <select
            value={filters.source_tab ?? ""}
            onChange={(e) => updateFilter({ source_tab: e.target.value || undefined })}
          >
            <option value="">All Sources</option>
            {SOURCE_TABS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>

          <MoreFiltersPopover
            csr={filters.csr}
            chat_type_id={filters.chat_type_id}
            status_id={filters.status_id}
            teams={filters.teams}
            ticket_number={filters.ticket_number}
            job_details={filters.job_details}
            address={filters.address}
            time_start_from={filters.time_start_from}
            time_start_to={filters.time_start_to}
            csrs={csrs}
            chatTypeOptions={chatTypeOptions.options}
            statusOptions={statusOptions.options}
            onChange={(patch) => updateFilter(patch)}
          />

          {hasActive && (
            <button
              type="button"
              className="filter-clear-all"
              onClick={clearFilters}
              title="Clear all filters"
            >
              <FilterX size={15} />
            </button>
          )}
        </div>

        <div className="filters-right">
          <SearchFilterInput
            key={clearKey}
            value={filters.client}
            placeholder="Client"
            onChange={(client) => updateFilter({ client })}
          />
        </div>
      </div>

      <DataTable
        data={data}
        columns={columns}
        loading={loading}
        onRowClick={handleView}
        getKey={(row) => row.id}
        groupByDate={{
          getDate: (row) =>
            filters.sort_by === "done_at" && row.done_at
              ? row.done_at
              : row.date,
        }}
        fixedLayout
      />

      {pagination && (cursorHistory.length > 0 || pagination.has_next) && (
        <div className="pagination">
          <button
            disabled={cursorHistory.length === 0}
            onClick={handlePrev}
          >
            Previous
          </button>
          <span>
            Page {cursorHistory.length + 1}
          </span>
          <button
            disabled={!pagination.has_next}
            onClick={handleNext}
          >
            Next
          </button>
        </div>
      )}

      {showForm && formDispatch && (
        <div className="modal-overlay" onClick={formReadOnly ? closeForm : undefined}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <DispatchForm
              dispatch={formDispatch}
              readOnly={formReadOnly}
              onSubmit={handleSubmit}
              onCancel={closeForm}
              onEdit={handleEdit}
              onDelete={() => handleDelete(formDispatch)}
              loading={saving}
            />
          </div>
        </div>
      )}

      {deleteDispatchTarget && (
        <div className="modal-overlay">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <form className="form-modal" onSubmit={handleConfirmDeleteDispatch}>
              <div className="form-header">
                <h2>Delete Dispatch</h2>
              </div>
              <div className="form-body">
                <p className="delete-warning">
                  This will remove the dispatch record for <strong>{deleteDispatchTarget.client}</strong> from the system.
                </p>
                <div className="form-row">
                  <label>Type the client name to confirm</label>
                  <input
                    type="text"
                    value={deleteConfirmName}
                    onChange={(e) => setDeleteConfirmName(e.target.value)}
                    placeholder={deleteDispatchTarget.client}
                    disabled={deleteSaving}
                    autoFocus
                  />
                </div>
              </div>
              <div className="form-footer">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setDeleteDispatchTarget(null)}
                  disabled={deleteSaving}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-delete-submit"
                  disabled={deleteSaving || deleteConfirmName.trim() !== deleteDispatchTarget.client}
                >
                  {deleteSaving ? "Deleting..." : "Delete Dispatch"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
