import React, { useMemo } from "react";
import type { ConfigOption } from "../lib/types";
import "../styles/DataTable.css";

export function lightenHex(hex: string, amount: number): string {
  const n = parseInt(hex.slice(1), 16);
  const r = Math.round(((n >> 16) & 255) + (255 - ((n >> 16) & 255)) * amount);
  const g = Math.round(((n >> 8) & 255) + (255 - ((n >> 8) & 255)) * amount);
  const b = Math.round((n & 255) + (255 - (n & 255)) * amount);
  return `rgb(${r}, ${g}, ${b})`;
}

export function StatusCapsule({ option }: { option?: ConfigOption | null }) {
  const color = option?.color ?? "#94a3b8";
  return (
    <span className="config-capsule" style={{ backgroundColor: color }}>
      {option?.label ?? "Unknown"}
      {option && !option.active && (
        <span className="config-capsule-inactive-tag"> (inactive)</span>
      )}
    </span>
  );
}

interface Column<T> {
  key: keyof T | string;
  header: string;
  render?: (row: T) => React.ReactNode;
  headerClassName?: string;
  width?: string;
}

interface DateGrouping<T> {
  getDate: (row: T) => string | Date;
  formatDate?: (date: Date) => string;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  loading?: boolean;
  onRowClick?: (row: T) => void;
  getKey: (row: T) => number | string;
  emptyMessage?: string;
  groupByDate?: DateGrouping<T>;
  fixedLayout?: boolean;
}

function defaultFormatDate(date: Date): string {
  return date.toLocaleDateString();
}

function resolveDateKey(
  rowDate: string | Date,
  formatDate: (date: Date) => string
): string {
  const date = rowDate instanceof Date ? rowDate : new Date(rowDate);
  return formatDate(date);
}

export default function DataTable<T>({
  data,
  columns,
  loading,
  onRowClick,
  getKey,
  emptyMessage,
  groupByDate,
  fixedLayout,
}: DataTableProps<T>) {
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const el = containerRef.current;
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

  const rowColorCoding = localStorage.getItem("rowColorCoding") === "true";

  const tableMinWidth = useMemo(() => {
    return columns.reduce((sum, col) => {
      if (!col.width) return sum;
      const pxMatch = typeof col.width === "string" && col.width.match(/^(\d+)px$/);
      return pxMatch ? sum + parseInt(pxMatch[1], 10) : sum;
    }, 0);
  }, [columns]);

  const isInitialLoad = loading && data.length === 0;
  const isRefreshing = loading && data.length > 0;

  if (isInitialLoad) {
    return (
      <div ref={containerRef}>
        <div className="table-loading">
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div ref={containerRef}>
        <div className="table-empty">
          <p>{emptyMessage || "No records found"}</p>
        </div>
      </div>
    );
  }

  const formatDate = groupByDate?.formatDate ?? defaultFormatDate;
  const rows: React.ReactNode[] = [];

  data.forEach((row, index) => {
    if (groupByDate) {
      const currentKey = resolveDateKey(groupByDate.getDate(row), formatDate);
      const previousKey =
        index > 0
          ? resolveDateKey(groupByDate.getDate(data[index - 1]), formatDate)
          : null;

      if (index > 0 && currentKey !== previousKey) {
        rows.push(
          <tr key={`divider-${currentKey}-${index}`} className="date-divider-row">
            <td colSpan={columns.length}>
              <div className="date-divider">
                <span className="date-divider-line" />
              </div>
            </td>
          </tr>
        );
      }
    }

    let rowBackground: string | undefined;
    if (rowColorCoding) {
      const statusOption = (row as Record<string, unknown>)
        .statusOption as ConfigOption | undefined;
      if (statusOption?.color) {
        rowBackground = lightenHex(statusOption.color, 0.9);
      }
    }

    rows.push(
      <tr
        key={getKey(row)}
        onClick={() => onRowClick?.(row)}
        className={onRowClick ? "clickable" : ""}
        style={rowBackground ? { backgroundColor: rowBackground } : undefined}
      >
        {columns.map((col) => {
          const key = String(col.key);
          const rawValue = (row as Record<string, unknown>)[key];
          let cell: React.ReactNode;

          if (col.render) {
            cell = col.render(row);
          } else if (rawValue === undefined || rawValue === null) {
            cell = "";
          } else if (
            key === "statusOption" ||
            key === "typeOption" ||
            key === "chatTypeOption"
          ) {
            cell = <StatusCapsule option={rawValue as ConfigOption | null} />;
          } else {
            cell = String(rawValue);
          }

          return <td key={key}>{cell}</td>;
        })}
      </tr>
    );
  });

  return (
    <div className="table-container" ref={containerRef}>
      {isRefreshing && <div className="table-refreshing">Refreshing…</div>}
      <table
        className={`data-table${fixedLayout ? " fixed" : ""}`}
        style={tableMinWidth > 0 ? { minWidth: tableMinWidth } : undefined}
      >
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={String(col.key)}
                style={col.width ? { width: col.width } : undefined}
                className={col.headerClassName}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  );
}