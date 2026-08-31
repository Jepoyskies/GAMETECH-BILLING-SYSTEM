import { useEffect, useRef, useState } from "react";
import api from "../../lib/api";
import { useToast } from "../../context/ToastContext";
import "../../styles/ListPage.css";
import "../../styles/ExportMonthDropdown.css";

interface ExportMonthDropdownProps {
  resourcePath: string;
  filePrefix: string;
  filterParams: URLSearchParams;
}

function formatMonthLabel(month: string): string {
  const [year, mon] = month.split("-").map(Number);
  const d = new Date(Date.UTC(year, mon - 1, 1));
  return d.toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
}

export default function ExportMonthDropdown({
  resourcePath,
  filePrefix,
  filterParams,
}: ExportMonthDropdownProps) {
  const { addToast } = useToast();
  const [open, setOpen] = useState(false);
  const [months, setMonths] = useState<string[]>([]);
  const [loadingMonths, setLoadingMonths] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [formatPickerMonth, setFormatPickerMonth] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (error) addToast(error, "error");
  }, [error]);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
        setFormatPickerMonth(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const openDropdown = async () => {
    setOpen((v) => !v);
    setFormatPickerMonth(null);
    if (months.length > 0) return;
    try {
      setLoadingMonths(true);
      setError(null);
      const params = new URLSearchParams(filterParams);
      const res = await api.get(`${resourcePath}/export/months?${params}`);
      setMonths(res.data.data as string[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load available months");
    } finally {
      setLoadingMonths(false);
    }
  };

  const handleExport = async (month: string, format: "csv" | "excel") => {
    try {
      setExporting(month);
      setError(null);
      const params = new URLSearchParams(filterParams);
      params.set("month", month);
      const endpoint = format === "excel" ? `${resourcePath}/export/excel` : `${resourcePath}/export`;
      const res = await api.get(`${endpoint}?${params}`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      const ext = format === "excel" ? "xlsx" : "csv";
      link.download = `${filePrefix}_${month}.${ext}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setOpen(false);
      setFormatPickerMonth(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="export-dropdown" ref={containerRef}>
      <button
        type="button"
        className={`btn-primary${open ? " active" : ""}`}
        onClick={openDropdown}
      >
        Export
      </button>

      {open && (
        <div className="export-dropdown-popover">
          {loadingMonths ? (
            <div className="export-dropdown-list">
              <span className="export-dropdown-empty">Loading months…</span>
            </div>
          ) : months.length === 0 ? (
            <div className="export-dropdown-list">
              <span className="export-dropdown-empty">No data available to export</span>
            </div>
          ) : (
            <div className="export-dropdown-list">
              {months.map((month) => (
                formatPickerMonth === month ? (
                  <div key={month} className="export-format-picker">
                    <span className="export-format-label">{formatMonthLabel(month)}</span>
                    <div className="export-format-actions">
                      <button
                        type="button"
                        className="export-format-btn csv"
                        disabled={exporting !== null}
                        onClick={() => handleExport(month, "csv")}
                      >
                        {exporting === month ? "…" : "CSV"}
                      </button>
                      <button
                        type="button"
                        className="export-format-btn excel"
                        disabled={exporting !== null}
                        onClick={() => handleExport(month, "excel")}
                      >
                        {exporting === month ? "…" : "Excel"}
                      </button>
                      <button
                        type="button"
                        className="export-format-back"
                        disabled={exporting !== null}
                        onClick={() => setFormatPickerMonth(null)}
                      >
                        ←
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    key={month}
                    type="button"
                    className="export-dropdown-option"
                    disabled={exporting !== null}
                    onClick={() => setFormatPickerMonth(month)}
                  >
                    {formatMonthLabel(month)}
                  </button>
                )
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}