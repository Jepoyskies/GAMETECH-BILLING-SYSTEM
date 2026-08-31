import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import { X, Send, Undo, CheckCircle } from "lucide-react";
import { useMonitoring, MonitoringFilters } from "../hooks/useMonitoring";
import { useCSR } from "../hooks/useCSR";
import { useConfigOptions } from "../hooks/useConfigOptions";
import { useToast } from "../context/ToastContext";
import DataTable from "./DataTable";
import MonitoringForm, { MonitoringFormData } from "./MonitoringForm";
import QuickDispatch, { DispatchFormData } from "./QuickDispatch";
import CompletionForm, { CompletionFormData } from "./CompletionForm";
import DateRangePicker from "./filters/DateRangePicker";
import SearchFilterInput from "./filters/SearchFilterInput";
import { buildColumnsFromKeys, Column } from "../lib/monitoringColumns";
import type { MonitoringRecord, ConfigListModule } from "../lib/types";
import "../styles/ListPage.css";

interface MonitoringListPageProps {
  tabType: string;
  title: string;
  icon?: React.ElementType;
  newButtonLabel?: string;
  pendingColumnKeys: string[];
  ongoingColumnKeys: string[];
}

function getMonitoringFiltersKey(tabType: string): string {
  return `monitoringListFilters_${tabType}`;
}

function loadMonitoringFilters(tabType: string): Omit<MonitoringFilters, "ongoing" | "page"> {
  const defaults: Omit<MonitoringFilters, "ongoing" | "page"> = {
    tab_type: tabType,
    done: false,
    limit: 100,
  };
  try {
    const stored = localStorage.getItem(getMonitoringFiltersKey(tabType));
    if (stored) return { ...defaults, ...JSON.parse(stored) };
  } catch { /* ignore */ }
  return defaults;
}

export default function MonitoringListPage({
  tabType,
  title,
  icon: Icon,
  newButtonLabel = "+ New Record",
  pendingColumnKeys,
  ongoingColumnKeys,
}: MonitoringListPageProps) {

  const { addToast } = useToast();
  const undispatchClickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [sharedFilters, setSharedFilters] = useState<Omit<MonitoringFilters, "ongoing" | "page">>(() => loadMonitoringFilters(tabType));

  const [notOngoingPage, setNotOngoingPage] = useState(1);
  const [ongoingPage, setOngoingPage] = useState(1);
  const [activeTab, setActiveTab] = useState<"pending" | "ongoing">("pending");

  const notOngoingFilters = useMemo<MonitoringFilters>(
    () => ({ ...sharedFilters, ongoing: false, page: notOngoingPage }),
    [sharedFilters, notOngoingPage]
  );

  const ongoingFilters = useMemo<MonitoringFilters>(
    () => ({ ...sharedFilters, ongoing: true, page: ongoingPage }),
    [sharedFilters, ongoingPage]
  );

  const [showForm, setShowForm] = useState(false);
  const [formRecord, setFormRecord] = useState<MonitoringRecord | null>(null);
  const [formReadOnly, setFormReadOnly] = useState(false);
  const [saving, setSaving] = useState(false);

  const [dispatchTarget, setDispatchTarget] = useState<MonitoringRecord | null>(null);
  const [dispatchSaving, setDispatchSaving] = useState(false);

  const [completionTarget, setCompletionTarget] = useState<MonitoringRecord | null>(null);
  const [completionSaving, setCompletionSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<MonitoringRecord | null>(null);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [deleteSaving, setDeleteSaving] = useState(false);

  const [cancelTarget, setCancelTarget] = useState<MonitoringRecord | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelSaving, setCancelSaving] = useState(false);

  const showTicketNumber = tabType === "CLIENT_CONCERNS";
  const showJobOrder = tabType === "INTERNET_INSTALL" || tabType === "CIGNAL_PLAY";

  const { data: csrs } = useCSR();
  const statusModule = tabType === "DISPATCH" ? "DISPATCH" : "MONITORING";
  const statusOptions = useConfigOptions("STATUS", statusModule as ConfigListModule);

  const {
    data: notOngoing,
    pagination: notOngoingPagination,
    loading: notOngoingLoading,
    createRecord,
    updateRecord,
    markAsDone,
    cancelRecord,
    deleteRecord,
  } = useMonitoring(notOngoingFilters);

  const {
    data: ongoing,
    pagination: ongoingPagination,
    loading: ongoingLoading,
    refetch: refetchOngoing,
  } = useMonitoring(ongoingFilters);

  const updateFilter = useCallback((patch: Partial<Omit<MonitoringFilters, "ongoing" | "page">>) => {
    setSharedFilters((f) => ({ ...f, ...patch }));
    setNotOngoingPage(1);
    setOngoingPage(1);
  }, []);

  useEffect(() => {
    const { tab_type: _, ...toStore } = sharedFilters;
    localStorage.setItem(getMonitoringFiltersKey(tabType), JSON.stringify(toStore));
  }, [sharedFilters, tabType]);

  const closeForm = () => {
    setShowForm(false);
    setFormRecord(null);
    setFormReadOnly(false);
  };

  const handleNew = () => {
    setFormRecord(null);
    setFormReadOnly(false);
    setShowForm(true);
  };

  const handleView = (row: MonitoringRecord) => {
    setFormRecord(row);
    setFormReadOnly(true);
    setShowForm(true);
  };

  const handleSubmit = async (formData: MonitoringFormData) => {
    try {
      setSaving(true);
      if (formRecord) {
        await updateRecord(formRecord.id, { ...formData });
        closeForm();
        addToast("Record updated successfully", "success");
      } else {
        await createRecord({ ...formData, tab_type: tabType });
        refetchOngoing();
        closeForm();
        addToast("Record created successfully", "success");
      }
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to save", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDispatchClick = (row: MonitoringRecord) => {
    setDispatchTarget(row);
  };

  const handleMarkDoneClick = (row: MonitoringRecord) => {
    setCompletionTarget(row);
  };

  const closeDispatchModal = () => {
    setDispatchTarget(null);
  };

  const closeCompletionModal = () => {
    setCompletionTarget(null);
  };

  const handleUndispatch = async (record: MonitoringRecord) => {
    if (!record) return;
    try {
      setDispatchSaving(true);

      await updateRecord(record.id, {
        time_start: null,
        time_accomplish: null,
        teams: [],
      });
      refetchOngoing();

      addToast(`Record for ${record.client} undispatched and moved back to Pending list.`, "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to undispatch", "error");
    } finally {
      setDispatchSaving(false);
    }
  };

  const handleDispatchConfirm = async (formData: DispatchFormData) => {
    if (!dispatchTarget) return;
    try {
      setDispatchSaving(true);

      await updateRecord(dispatchTarget.id, {
        time_start: formData.time_start,
        time_accomplish: formData.time_accomplish,
        teams: formData.teams,
      });

      addToast(
        `Record for ${dispatchTarget.client} dispatched and moved to Ongoing records.`,
        "success"
      );

      refetchOngoing();

      setDispatchTarget(null);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to save dispatch info", "error");
    } finally {
      setDispatchSaving(false);
    }
  };

  const handleCompletionConfirm = async (formData: CompletionFormData) => {
    if (!completionTarget) return;
    try {
      setCompletionSaving(true);

      const jobDetail: Record<string, string | null> = {
        nap_port: formData.nap_port || null,
        cable_length: formData.cable_length || null,
        nap_reading: formData.nap_reading || null,
        pole_number: formData.pole_number || null,
        plan_package: formData.plan_package || null,
        ont_modem_sn: formData.ont_modem_sn || null,
        signal_level: formData.signal_level || null,
        facility: formData.facility || null,
        house_reading: formData.house_reading || null,
        special_instruction: formData.special_instruction || null,
        technician_remarks: formData.technician_remarks || null,
        acknowledged_by: formData.acknowledged_by || null,
      };

      const result = await markAsDone(completionTarget.id, {
        time_start: formData.time_start,
        time_accomplish: formData.time_accomplish,
        teams: formData.teams,
        jobDetail,
      });

      refetchOngoing();
      addToast(
        `Record for ${result.record.client} marked as Done and moved to Dispatch Log (Dispatch #${result.dispatch.id}).`,
        "success"
      );
      setCompletionTarget(null);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to mark as done", "error");
    } finally {
      setCompletionSaving(false);
    }
  };

  const handleDelete = (record: MonitoringRecord) => {
    setDeleteTarget(record);
    setDeleteConfirmName("");
  };

  const handleCancelClick = (record: MonitoringRecord) => {
    setCancelTarget(record);
    setCancelReason("");
  };

  const handleConfirmCancel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancelTarget) return;
    try {
      setCancelSaving(true);
      const result = await cancelRecord(cancelTarget.id, cancelReason.trim());
      refetchOngoing();
      addToast(
        `Record for ${result.record.client} cancelled and moved to Dispatch Log (Dispatch #${result.dispatch.id}).`,
        "success"
      );
      setCancelTarget(null);
      setCancelReason("");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to cancel", "error");
    } finally {
      setCancelSaving(false);
    }
  };

  const handleConfirmDelete = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deleteTarget) return;
    try {
      setDeleteSaving(true);
      await deleteRecord(deleteTarget.id, deleteConfirmName.trim());
      refetchOngoing();
      addToast("Record deleted successfully", "success");
      setDeleteTarget(null);
      setDeleteConfirmName("");
      if (formRecord?.id === deleteTarget.id) closeForm();
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to delete", "error");
    } finally {
      setDeleteSaving(false);
    }
  };

  const injectActions = (cols: Column[], group: "notOngoing" | "ongoing"): Column[] =>
    cols.map((col) =>
      col.key !== "actions"
        ? col
        : {
            ...col,
            render: (row: MonitoringRecord) => (
              <div className="row-actions">
                {group === "notOngoing" ? (
                  <>
                    <button
                      className="btn-icon btn-icon-cancel"
                      title="Cancel"
                      onClick={(e) => { e.stopPropagation(); handleCancelClick(row); }}
                    >
                      <X size={15} />
                    </button>
                    <button
                      className="btn-icon btn-icon-dispatch"
                      title="Dispatch"
                      onClick={(e) => { e.stopPropagation(); handleDispatchClick(row); }}
                    >
                      <Send size={15} />
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      className="btn-icon btn-icon-undispatch"
                      title="Undispatch (double-click)"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (undispatchClickTimer.current) {
                          clearTimeout(undispatchClickTimer.current);
                          undispatchClickTimer.current = null;
                          return;
                        }
                        undispatchClickTimer.current = setTimeout(() => {
                          undispatchClickTimer.current = null;
                          addToast("Double-click to undispatch this record", "info");
                        }, 300);
                      }}
                      onDoubleClick={(e) => {
                        e.stopPropagation();
                        if (undispatchClickTimer.current) {
                          clearTimeout(undispatchClickTimer.current);
                          undispatchClickTimer.current = null;
                        }
                        handleUndispatch(row);
                      }}
                    >
                      <Undo size={15} />
                    </button>
                    <button
                      className="btn-icon btn-icon-done"
                      title="Mark as Done"
                      onClick={(e) => { e.stopPropagation(); handleMarkDoneClick(row); }}
                    >
                      <CheckCircle size={15} />
                    </button>
                  </>
                )}
              </div>
            ),
          }
    );

  const notOngoingColumns = injectActions(buildColumnsFromKeys(pendingColumnKeys), "notOngoing");
  const renderedOngoingColumns = injectActions(buildColumnsFromKeys(ongoingColumnKeys), "ongoing");

  return (
    <div className="list-page">

      {/* ── Header ── */}
      <div className="list-header">
        <h1>{Icon && <Icon size={24} />} {title}</h1>
        <button className="btn-primary" onClick={handleNew}>{newButtonLabel}</button>
      </div>

      {/* ── Filters ── */}
      <div className="filters">
        <div className="filters-left">
          <DateRangePicker
            dateFrom={sharedFilters.date_from}
            dateTo={sharedFilters.date_to}
            onChange={({ date_from, date_to }) => updateFilter({ date_from, date_to })}
          />

          <select
            value={sharedFilters.csr || ""}
            onChange={(e) =>
              updateFilter({ csr: e.target.value ? Number(e.target.value) : undefined })
            }
          >
            <option value="">All CSRs</option>
            {csrs.map((csr) => (
              <option key={csr.id} value={csr.id}>{csr.name}</option>
            ))}
          </select>

          <select
            value={sharedFilters.status_id ?? ""}
            onChange={(e) =>
              updateFilter({ status_id: e.target.value ? Number(e.target.value) : undefined })
            }
          >
            <option value="">All Statuses</option>
            {statusOptions.options.map((s) => (
              <option key={s.id} value={s.id}>{s.label}</option>
            ))}
          </select>
        </div>

        <div className="filters-right">
          <SearchFilterInput
            value={sharedFilters.client}
            placeholder="Client"
            onChange={(client) => updateFilter({ client })}
          />

          {showTicketNumber && (
            <SearchFilterInput
              value={sharedFilters.ticket_number}
              placeholder="Ticket No."
              onChange={(ticket_number) => updateFilter({ ticket_number })}
            />
          )}

          {showJobOrder && (
            <SearchFilterInput
              value={sharedFilters.job_order}
              placeholder="Job Order No."
              onChange={(job_order) => updateFilter({ job_order })}
            />
          )}
        </div>
      </div>

      {/* ── Tab toggle buttons ── */}
      <div className="tab-toggle">
        <button
          className={activeTab === "pending" ? "active" : ""}
          onClick={() => setActiveTab("pending")}
        >
          Pending
          <span className="tab-count">{notOngoingPagination?.total ?? 0}</span>
        </button>
        <button
          className={activeTab === "ongoing" ? "active" : ""}
          onClick={() => setActiveTab("ongoing")}
        >
          Ongoing
          <span className="tab-count">{ongoingPagination?.total ?? 0}</span>
        </button>
      </div>

      {/* ── Tab content ── */}
      {activeTab === "pending" && (
        <DataTable
          data={notOngoing}
          columns={notOngoingColumns}
          loading={notOngoingLoading}
          onRowClick={handleView}
          getKey={(row) => row.id}
          fixedLayout
        />
      )}
      {activeTab === "ongoing" && (
        <DataTable
          data={ongoing}
          columns={renderedOngoingColumns}
          loading={ongoingLoading}
          onRowClick={handleView}
          getKey={(row) => row.id}
          fixedLayout
        />
      )}

      {/* ── Pagination ── */}
      {activeTab === "pending" && notOngoingPagination && notOngoingPagination.total_pages > 1 && (
        <div className="pagination">
          <button
            disabled={notOngoingPagination.page <= 1}
            onClick={() => setNotOngoingPage((p) => p - 1)}
          >
            Previous
          </button>
          <span>Page {notOngoingPagination.page} of {notOngoingPagination.total_pages}</span>
          <button
            disabled={notOngoingPagination.page >= notOngoingPagination.total_pages}
            onClick={() => setNotOngoingPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}
      {activeTab === "ongoing" && ongoingPagination && ongoingPagination.total_pages > 1 && (
        <div className="pagination">
          <button
            disabled={ongoingPagination.page <= 1}
            onClick={() => setOngoingPage((p) => p - 1)}
          >
            Previous
          </button>
          <span>Page {ongoingPagination.page} of {ongoingPagination.total_pages}</span>
          <button
            disabled={ongoingPagination.page >= ongoingPagination.total_pages}
            onClick={() => setOngoingPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}

      {/* ── Create / Edit form modal ── */}
      {showForm && (
        <div className="modal-overlay" onClick={formReadOnly ? closeForm : undefined}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <MonitoringForm
              record={formRecord}
              tabType={tabType}
              readOnly={formReadOnly}
              onSubmit={handleSubmit}
              onCancel={closeForm}
              onDelete={() => formRecord && handleDelete(formRecord)}
              onEdit={() => setFormReadOnly(false)}
              loading={saving}
              ongoing={!!formRecord?.time_start}
            />
          </div>
        </div>
      )}

      {/* ── Dispatch modal ── */}
      {dispatchTarget && (
        <QuickDispatch
          record={dispatchTarget}
          onConfirm={handleDispatchConfirm}
          onCancel={closeDispatchModal}
          loading={dispatchSaving}
        />
      )}

      {/* ── Completion form ── */}
      {completionTarget && (
        <CompletionForm
          record={completionTarget}
          onConfirm={handleCompletionConfirm}
          onCancel={closeCompletionModal}
          loading={completionSaving}
        />
      )}

      {/* ── Delete confirmation modal ── */}
      {deleteTarget && (
        <div className="modal-overlay">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <form className="form-modal" onSubmit={handleConfirmDelete}>
              <div className="form-header">
                <h2>Delete Record</h2>
              </div>
              <div className="form-body">
                <p className="delete-warning">
                  This will permanently remove the record for{" "}
                  <strong>{deleteTarget.client}</strong>.
                </p>
                <div className="form-row">
                  <label>Type the client name to confirm</label>
                  <input
                    type="text"
                    value={deleteConfirmName}
                    onChange={(e) => setDeleteConfirmName(e.target.value)}
                    placeholder={deleteTarget.client}
                    disabled={deleteSaving}
                    autoFocus
                  />
                </div>
              </div>
              <div className="form-footer">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setDeleteTarget(null)}
                  disabled={deleteSaving}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-delete-submit"
                  disabled={deleteSaving || deleteConfirmName.trim() !== deleteTarget.client}
                >
                  {deleteSaving ? "Deleting..." : "Delete Record"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Cancel confirmation modal ── */}
      {cancelTarget && (
        <div className="modal-overlay">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <form className="form-modal" onSubmit={handleConfirmCancel}>
              <div className="form-header">
                <h2>Cancel Dispatch</h2>
              </div>
              <div className="form-body">
                <p className="delete-warning">
                  Are you sure you want to cancel this dispatch for{" "}
                  <strong>{cancelTarget.client}</strong>?
                </p>
                <div className="form-row">
                  <label>Reason (required)</label>
                  <textarea
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    placeholder="Enter reason for cancellation"
                    disabled={cancelSaving}
                    autoFocus
                    rows={3}
                  />
                </div>
              </div>
              <div className="form-footer">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setCancelTarget(null)}
                  disabled={cancelSaving}
                >
                  Back
                </button>
                <button
                  type="submit"
                  className="btn-delete-submit"
                  disabled={cancelSaving || !cancelReason.trim()}
                >
                  {cancelSaving ? "Cancelling..." : "Cancel Dispatch"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}