import { useEffect, useState, useCallback, useRef } from "react";
import { Download, Eye, EyeOff, HardDrive, Upload } from "lucide-react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import DataTable from "../components/DataTable";
import type { BackupHistoryEntry } from "../lib/types";
import "../styles/ListPage.css";
import "../styles/Backups.css";
import "../styles/Forms.css";

type FilterMode = "all" | "full" | "hourly" | "restore" | "presafety";
type ActiveTab = "history" | "restore";

export default function Backups() {
  const { isSuperAdmin } = useAuth();
  const { addToast } = useToast();
  const [activeTab, setActiveTab] = useState<ActiveTab>("history");
  const [data, setData] = useState<BackupHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterMode>("all");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const limit = 31;
  const [restoreFiles, setRestoreFiles] = useState<BackupHistoryEntry[]>([]);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [presafetyFiles, setPresafetyFiles] = useState<BackupHistoryEntry[]>([]);
  const [presafetyLoading, setPresafetyLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importTarget, setImportTarget] = useState<{
    temp_id: string;
    original_filename: string;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [directory, setDirectory] = useState("");
  const [savingDir, setSavingDir] = useState(false);
  const directoryRef = useRef(directory);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoreTarget, setRestoreTarget] = useState<BackupHistoryEntry | null>(null);
  const [restorePassword, setRestorePassword] = useState("");
  const [showRestorePassword, setShowRestorePassword] = useState(false);
  const [importConfirmed, setImportConfirmed] = useState(false);

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true);
      const offset = (page - 1) * limit;
      const res = await api.get(`/backups/history?filter=${filter}&limit=${limit}&offset=${offset}`);
      setData(res.data.data);
      setTotal(res.data.total);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to load backup history", "error");
    } finally {
      setLoading(false);
    }
  }, [filter, page, addToast]);

  const fetchRestorable = useCallback(async () => {
    try {
      setRestoreLoading(true);
      const res = await api.get("/backups/restorable");
      setRestoreFiles(res.data.data);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to load restorable files", "error");
    } finally {
      setRestoreLoading(false);
    }
  }, [addToast]);

  const fetchPresafety = useCallback(async () => {
    try {
      setPresafetyLoading(true);
      const res = await api.get("/backups/presafety");
      setPresafetyFiles(res.data.data);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to load safety backups", "error");
    } finally {
      setPresafetyLoading(false);
    }
  }, [addToast]);

  const fetchDirectory = useCallback(async () => {
    try {
      const res = await api.get("/backups/directory");
      setDirectory(res.data.data.directory);
      directoryRef.current = res.data.data.directory;
    } catch {
      // Directory is optional
    }
  }, []);

  useEffect(() => {
    if (!isSuperAdmin) return;
    fetchDirectory();
  }, [isSuperAdmin, fetchDirectory]);

  useEffect(() => {
    if (!isSuperAdmin || activeTab !== "history") return;
    fetchHistory();
  }, [isSuperAdmin, activeTab, fetchHistory]);

  useEffect(() => {
    if (!isSuperAdmin || activeTab !== "restore") return;
    fetchRestorable();
    fetchPresafety();
  }, [isSuperAdmin, activeTab, fetchRestorable, fetchPresafety]);

  const handleManualBackup = async () => {
    try {
      setCreating(true);
      await api.post("/backups/manual", { directory: directory || undefined });
      addToast("Manual full backup completed successfully", "success");
      if (activeTab === "history") fetchHistory();
      if (activeTab === "restore") fetchRestorable();
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Backup failed", "error");
    } finally {
      setCreating(false);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImporting(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("/backups/validate-import", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setImportTarget({
        temp_id: res.data.data.temp_id,
        original_filename: res.data.data.original_filename,
      });
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Invalid or incompatible backup file", "error");
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleRestore = async () => {
    if (!restorePassword) return;
    if (importTarget && !importConfirmed) return;
    try {
      setRestoring(true);
      const endpoint = restoreTarget ? "/backups/restore" : "/backups/import-restore";
      const body = restoreTarget
        ? { history_id: restoreTarget.id, current_password: restorePassword }
        : { temp_id: importTarget!.temp_id, original_filename: importTarget!.original_filename, current_password: restorePassword };
      const res = await api.post(endpoint, body);
      const msg = res.data.data?.message || "Database restored successfully";
      addToast(msg, "success");
      setRestoreTarget(null);
      setImportTarget(null);
      setRestorePassword("");
      setImportConfirmed(false);
      fetchHistory();
      fetchRestorable();
      fetchPresafety();
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Restore failed", "error");
    } finally {
      setRestoring(false);
    }
  };

  const saveDirectory = useCallback(async () => {
    const val = directory.trim();
    if (!val || val === directoryRef.current) return;
    try {
      setSavingDir(true);
      await api.put("/backups/directory", { directory: val });
      directoryRef.current = val;
      addToast("Backup directory saved", "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to save directory", "error");
    } finally {
      setSavingDir(false);
    }
  }, [directory, addToast]);

  const handleCloseModal = () => {
    setRestoreTarget(null);
    setImportTarget(null);
    setRestorePassword("");
    setImportConfirmed(false);
  };

  if (!isSuperAdmin) {
    return (
      <div className="list-page">
        <div className="list-header">
          <h1><HardDrive size={24} /> Backups</h1>
        </div>
        <p className="period-meta">You do not have permission to access this page.</p>
      </div>
    );
  }

  const filterOptions: { key: FilterMode; label: string }[] = [
    { key: "all", label: "All" },
    { key: "full", label: "Full" },
    { key: "hourly", label: "Hourly" },
    { key: "restore", label: "Restore" },
    { key: "presafety", label: "Safety" },
  ];

  const typeLabel = (t: string) =>
    t === "FULL" ? "Full" : t === "HOURLY" ? "Hourly" : t === "PRESAFETY" ? "Safety" : t === "RESTORE" ? "Restore" : t;
  const typeBadge = (t: string) =>
    t === "FULL" ? "badge-full" : t === "HOURLY" ? "badge-hourly" : t === "PRESAFETY" ? "badge-presafety" : "badge-restore";
  const triggerLabel = (t: string) =>
    t === "SCHEDULED" ? "Scheduled" : t === "MANUAL" ? "Manual" : t === "PRESAFETY" ? "Safety" : t === "RESTORE" ? "Restore" : t;

  const historyColumns = [
    { key: "id", header: "ID", width: "60px" },
    {
      key: "backup_type",
      header: "Type",
      width: "80px",
      render: (row: BackupHistoryEntry) => (
        <span className={`backup-type-badge ${typeBadge(row.backup_type)}`}>
          {typeLabel(row.backup_type)}
        </span>
      ),
    },
    {
      key: "trigger_source",
      header: "Trigger",
      width: "100px",
      render: (row: BackupHistoryEntry) =>
        triggerLabel(row.trigger_source),
    },
    {
      key: "status",
      header: "Status",
      width: "90px",
      render: (row: BackupHistoryEntry) => (
        <span className={`backup-status-badge ${row.status === "SUCCESS" ? "badge-success" : "badge-failed"}`}>
          {row.status === "SUCCESS" ? "Success" : "Failed"}
        </span>
      ),
    },
    { key: "filename", header: "Filename" },
    {
      key: "file_size",
      header: "Size",
      width: "100px",
      render: (row: BackupHistoryEntry) => {
        if (!row.file_size) return "—";
        const bytes = parseInt(row.file_size, 10);
        if (isNaN(bytes)) return row.file_size;
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
      },
    },
    {
      key: "error_message",
      header: "Error",
      render: (row: BackupHistoryEntry) =>
        row.error_message ? (
          <span className="backup-error-text" title={row.error_message}>
            {row.error_message.length > 60
              ? `${row.error_message.slice(0, 60)}...`
              : row.error_message}
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "created_at",
      header: "Created At",
      width: "170px",
      render: (row: BackupHistoryEntry) => new Date(row.created_at).toLocaleString(),
    },
  ];

  const restoreColumns = [
    { key: "id", header: "ID", width: "60px" },
    {
      key: "backup_type",
      header: "Type",
      width: "80px",
      render: (row: BackupHistoryEntry) => (
        <span className={`backup-type-badge ${typeBadge(row.backup_type)}`}>
          {typeLabel(row.backup_type)}
        </span>
      ),
    },
    {
      key: "directory",
      header: "File Path",
      render: (row: BackupHistoryEntry) => `${row.directory}\\${row.filename}`,
    },
    {
      key: "file_size",
      header: "Size",
      width: "100px",
      render: (row: BackupHistoryEntry) => {
        if (!row.file_size) return "—";
        const bytes = parseInt(row.file_size, 10);
        if (isNaN(bytes)) return row.file_size;
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
      },
    },
    {
      key: "created_at",
      header: "Created At",
      width: "170px",
      render: (row: BackupHistoryEntry) => new Date(row.created_at).toLocaleString(),
    },
    {
      key: "actions",
      header: "Actions",
      width: "100px",
      render: (row: BackupHistoryEntry) => (
        <div className="row-actions">
          <button
            className="btn-icon btn-icon-download"
            onClick={(e) => {
              e.stopPropagation();
              const a = document.createElement("a");
              a.href = `/api/backups/download/${row.id}`;
              a.download = row.filename;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
            }}
            title="Download backup file"
          >
            <Download size={14} />
          </button>
          <button
            className="btn-restore"
            onClick={(e) => {
              e.stopPropagation();
              setRestoreTarget(row);
            }}
          >
            Restore
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="list-page">
      <div className="list-header">
        <h1><HardDrive size={24} /> Backups</h1>
        <div className="filters-right">
          <label className="dir-label">Directory:</label>
          <input
            type="text"
            className="dir-input"
            value={directory}
            onChange={(e) => setDirectory(e.target.value)}
            onBlur={saveDirectory}
            placeholder="Backup directory path"
          />
          {savingDir && <span className="saving-indicator">saving…</span>}
        </div>
      </div>

      <div className="tabs">
        <button
          className={`tab-btn ${activeTab === "history" ? "active" : ""}`}
          onClick={() => setActiveTab("history")}
        >
          Backup History
        </button>
        <button
          className={`tab-btn ${activeTab === "restore" ? "active" : ""}`}
          onClick={() => setActiveTab("restore")}
        >
          Backup Files
        </button>
      </div>

        {activeTab === "history" && (
          <div className="tab-content">
            <select
              className="backup-filter-select"
              value={filter}
              onChange={(e) => { setFilter(e.target.value as FilterMode); setPage(1); }}
            >
              {filterOptions.map((opt) => (
                <option key={opt.key} value={opt.key}>{opt.label}</option>
              ))}
            </select>
            <DataTable
              data={data}
              columns={historyColumns}
              loading={loading}
              getKey={(row) => row.id}
              emptyMessage="No backup history found"
            />
          </div>
        )}

        {activeTab === "restore" && (
          <div className="tab-content">
            <div className="list-header">
              <h2>Daily Backups</h2>
              <div className="header-actions">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".dump"
                  onChange={handleFileSelect}
                  style={{ display: "none" }}
                />
                <button
                  className="btn-secondary"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={importing}
                >
                  {importing ? "Validating…" : <><Upload size={14} /> Import</>}
                </button>
                <button
                  className="btn-primary"
                  onClick={handleManualBackup}
                  disabled={creating}
                >
                  {creating ? "Creating Backup…" : "+ Manual Full Backup"}
                </button>
              </div>
            </div>
            <DataTable
              data={restoreFiles.filter((r) => r.backup_type === "FULL")}
              columns={restoreColumns}
              loading={restoreLoading}
              getKey={(row) => row.id}
              emptyMessage="No full backup files found"
            />

            <div className="list-header" style={{ marginTop: "2rem" }}>
              <h2>Hourly Backups</h2>
            </div>
            <DataTable
              data={restoreFiles.filter((r) => r.backup_type === "HOURLY")}
              columns={restoreColumns}
              loading={restoreLoading}
              getKey={(row) => row.id}
              emptyMessage="No hourly backup files found"
            />

            <div className="list-header" style={{ marginTop: "2rem" }}>
              <h2>Safety Backups <span className="badge-subtitle">Auto-created before import restore (max 3 kept)</span></h2>
            </div>
            <DataTable
              data={presafetyFiles}
              columns={restoreColumns}
              loading={presafetyLoading}
              getKey={(row) => row.id}
              emptyMessage="No safety backups found"
            />
          </div>
        )}

        {activeTab === "history" && total > limit && (
          <div className="pagination" style={{ padding: "1rem 1.5rem" }}>
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span>
              Page {page} of {Math.ceil(total / limit)}
            </span>
            <button
              disabled={page >= Math.ceil(total / limit)}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        )}
        {(restoreTarget || importTarget) && (
          <div className="modal-overlay" onClick={handleCloseModal}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="form-modal danger">
                <div className="form-header">
                  <h2>{importTarget ? "Import & Restore Backup" : "Restore Backup"}</h2>
                </div>
                <div className="form-body">
                  <div className="form-section danger">
                    <p className="form-section-title">Destructive Action — Data Will Be Overwritten</p>
                    <p className="delete-warning">
                      Restoring the database from backup "<strong>{restoreTarget?.filename ?? importTarget?.original_filename}</strong>" will <strong>permanently overwrite</strong> all current operational data. Any changes made after this backup was created will be <strong>irreversibly lost</strong>.
                    </p>
                    <p className="delete-warning">
                      <strong>All currently logged-in users will be removed and replaced with the users from the backup.</strong> Everyone will be logged out immediately and must log in again with the restored accounts.
                    </p>
                    <p className="delete-warning">
                      This action <strong>cannot be undone</strong>. It is strongly recommended to create a full backup before proceeding.
                    </p>
                    {importTarget && (
                      <label className="checkbox-label" style={{ marginTop: "0.75rem" }}>
                        <input
                          type="checkbox"
                          checked={importConfirmed}
                          onChange={(e) => setImportConfirmed(e.target.checked)}
                          disabled={restoring}
                        />
                        <span>
                          I confirm that this backup is from the same Dispatch System.
                        </span>
                      </label>
                    )}
                  </div>

                  <div className="form-row" style={{ marginTop: "1rem" }}>
                    <label>Confirm with your password</label>
                    <div className="password-input-wrapper">
                      <input
                        type={showRestorePassword ? "text" : "password"}
                        value={restorePassword}
                        onChange={(e) => setRestorePassword(e.target.value)}
                        placeholder="Your SUPERADMIN password"
                        autoComplete="current-password"
                        disabled={restoring}
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowRestorePassword(!showRestorePassword)}
                        tabIndex={-1}
                      >
                        {showRestorePassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="form-footer">
                  <button
                    type="button"
                    className="btn-cancel"
                    onClick={handleCloseModal}
                    disabled={restoring}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn-delete-submit"
                    onClick={handleRestore}
                    disabled={restoring || !restorePassword || (!!importTarget && !importConfirmed)}
                  >
                    {restoring ? "Restoring…" : "Restore Database"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
    </div>
  );
}
