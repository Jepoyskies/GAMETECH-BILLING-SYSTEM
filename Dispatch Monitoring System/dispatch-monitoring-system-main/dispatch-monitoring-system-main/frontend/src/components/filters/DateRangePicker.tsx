import { useEffect, useRef, useState } from "react";
import "../../styles/Filters.css";

interface DateRangePickerProps {
  dateFrom?: string;
  dateTo?: string;
  onChange: (range: { date_from?: string; date_to?: string }) => void;
}

type Preset = "all" | "today" | "month" | "custom";

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function toIsoDay(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function todayRange(): { from: string; to: string } {
  const today = toIsoDay(new Date());
  return { from: today, to: today };
}

function thisMonthRange(): { from: string; to: string } {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return { from: toIsoDay(first), to: toIsoDay(last) };
}

function detectPreset(dateFrom?: string, dateTo?: string): Preset {
  if (!dateFrom && !dateTo) return "all";
  const today = todayRange();
  if (dateFrom === today.from && dateTo === today.to) return "today";
  const month = thisMonthRange();
  if (dateFrom === month.from && dateTo === month.to) return "month";
  return "custom";
}

function formatDisplayDate(value?: string) {
  if (!value) return "…";
  const d = new Date(value + "T00:00:00");
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function buttonLabel(preset: Preset, dateFrom?: string, dateTo?: string): string {
  switch (preset) {
    case "all":
      return "All Records";
    case "today":
      return "Today";
    case "month":
      return "This Month";
    default:
      return `${formatDisplayDate(dateFrom)} – ${formatDisplayDate(dateTo)}`;
  }
}

export default function DateRangePicker({
  dateFrom,
  dateTo,
  onChange,
}: DateRangePickerProps) {
  const [open, setOpen] = useState(false);
  const [draftFrom, setDraftFrom] = useState(dateFrom ?? "");
  const [draftTo, setDraftTo] = useState(dateTo ?? "");
  const containerRef = useRef<HTMLDivElement>(null);

  const activePreset = detectPreset(dateFrom, dateTo);
  const [showCustom, setShowCustom] = useState(activePreset === "custom");

  useEffect(() => {
    setDraftFrom(dateFrom ?? "");
    setDraftTo(dateTo ?? "");
  }, [dateFrom, dateTo]);

  useEffect(() => {
    if (!open) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const selectPreset = (preset: Preset) => {
    if (preset === "all") {
      onChange({ date_from: undefined, date_to: undefined });
      setShowCustom(false);
      setOpen(false);
      return;
    }
    if (preset === "today") {
      const { from, to } = todayRange();
      onChange({ date_from: from, date_to: to });
      setShowCustom(false);
      setOpen(false);
      return;
    }
    if (preset === "month") {
      const { from, to } = thisMonthRange();
      onChange({ date_from: from, date_to: to });
      setShowCustom(false);
      setOpen(false);
      return;
    }
    setShowCustom(true);
  };

  const applyCustom = () => {
    onChange({
      date_from: draftFrom || undefined,
      date_to: draftTo || undefined,
    });
    setOpen(false);
  };

  const label = buttonLabel(activePreset, dateFrom, dateTo);

  const presets: { key: Preset; label: string }[] = [
    { key: "all", label: "All Records" },
    { key: "today", label: "Today" },
    { key: "month", label: "This Month" },
    { key: "custom", label: "Custom Date Range" },
  ];

  return (
    <div className="filter-date-range" ref={containerRef}>
      <button
        type="button"
        className={`filter-date-range-btn${open ? " active" : ""}`}
        onClick={() => {
          setShowCustom(activePreset === "custom");
          setOpen((v) => !v);
        }}
      >
        {label}
      </button>

      {open && (
        <div className="filter-popover">
          <div className="filter-preset-list">
            {presets.map((p) => {
              const isActive =
                p.key === "custom" ? showCustom : activePreset === p.key && !showCustom;
              return (
                <button
                  key={p.key}
                  type="button"
                  className={`filter-preset-option${isActive ? " active" : ""}`}
                  onClick={() => selectPreset(p.key)}
                >
                  {p.label}
                </button>
              );
            })}
          </div>

          {showCustom && (
            <>
              <div className="filter-popover-row">
                <div className="filter-popover-field">
                  <label htmlFor="filter-date-from">Start</label>
                  <input
                    id="filter-date-from"
                    type="date"
                    value={draftFrom}
                    max={draftTo || undefined}
                    onChange={(e) => setDraftFrom(e.target.value)}
                  />
                </div>
                <div className="filter-popover-field">
                  <label htmlFor="filter-date-to">End</label>
                  <input
                    id="filter-date-to"
                    type="date"
                    value={draftTo}
                    min={draftFrom || undefined}
                    onChange={(e) => setDraftTo(e.target.value)}
                  />
                </div>
              </div>
              <div className="filter-popover-actions">
                <button
                  type="button"
                  className="filter-popover-clear"
                  onClick={() => {
                    setDraftFrom("");
                    setDraftTo("");
                    onChange({ date_from: undefined, date_to: undefined });
                    setShowCustom(false);
                    setOpen(false);
                  }}
                >
                  Clear
                </button>
                <button
                  type="button"
                  className="filter-popover-apply"
                  onClick={applyCustom}
                >
                  Apply
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
