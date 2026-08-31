import { useEffect, useRef, useState } from "react";
import type { CSR } from "../../lib/types";
import type { ConfigOption } from "../../lib/types";
import SearchFilterInput from "./SearchFilterInput";
import TeamMultiselectFilter from "./TeamMultiselectFilter";
import "../../styles/Filters.css";

interface MoreFiltersProps {
  csr?: number;
  chat_type_id?: number;
  status_id?: number;
  teams?: number[];
  ticket_number?: string;
  job_details?: string;
  address?: string;
  time_start_from?: string;
  time_start_to?: string;
  csrs: CSR[];
  chatTypeOptions: ConfigOption[];
  statusOptions: ConfigOption[];
  onChange: (patch: {
    csr?: number;
    chat_type_id?: number;
    status_id?: number;
    teams?: number[];
    ticket_number?: string;
    job_details?: string;
    address?: string;
    time_start_from?: string;
    time_start_to?: string;
  }) => void;
}

export default function MoreFiltersPopover({
  csr,
  chat_type_id,
  status_id,
  teams,
  ticket_number,
  job_details,
  address,
  time_start_from,
  time_start_to,
  csrs,
  chatTypeOptions,
  statusOptions,
  onChange,
}: MoreFiltersProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

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

  const activeCount = [csr, chat_type_id, status_id, teams, ticket_number, job_details, address, time_start_from, time_start_to].filter(
    (v) => v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0)
  ).length;

  return (
    <div className="filter-more" ref={containerRef}>
      <button
        type="button"
        className={`filter-more-btn${open ? " active" : ""}${activeCount > 0 ? " has-filters" : ""}`}
        onClick={() => setOpen((v) => !v)}
      >
        More Filters
        {activeCount > 0 && <span className="filter-more-badge">{activeCount}</span>}
      </button>

      {open && (
        <div className="filter-popover filter-more-popover">
          <div className="filter-more-grid">
            <div className="filter-more-field">
              <label>CSR</label>
              <select
                value={csr || ""}
                onChange={(e) =>
                  onChange({
                    csr: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              >
                <option value="">All CSRs</option>
                {csrs.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            <div className="filter-more-field">
              <label>Chat Type</label>
              <select
                value={chat_type_id ?? ""}
                onChange={(e) =>
                  onChange({ chat_type_id: e.target.value ? Number(e.target.value) : undefined })
                }
              >
                <option value="">All Chat Types</option>
                {chatTypeOptions.filter((t) => t.active).map((t) => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </select>
            </div>

            <div className="filter-more-field">
              <label>Status</label>
              <select
                value={status_id ?? ""}
                onChange={(e) =>
                  onChange({ status_id: e.target.value ? Number(e.target.value) : undefined })
                }
              >
                <option value="">All Statuses</option>
                {(statusOptions ?? []).filter((s) => s.active).map((s) => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </select>
            </div>

            <div className="filter-more-field">
              <label>Team</label>
              <TeamMultiselectFilter
                value={teams}
                onChange={(teamIds) => onChange({ teams: teamIds })}
              />
            </div>

            <div className="filter-more-field filter-more-field-wide">
              <label>Address</label>
              <SearchFilterInput
                value={address}
                placeholder="Address, Brgy/City"
                onChange={(address) => onChange({ address })}
              />
            </div>

            <div className="filter-more-field filter-more-field-wide">
              <label>Job Details</label>
              <SearchFilterInput
                value={job_details}
                placeholder="Job order, Acc number"
                onChange={(job_details) => onChange({ job_details })}
              />
            </div>

            <div className="filter-more-field filter-more-field-wide">
              <label>Ticket</label>
              <SearchFilterInput
                value={ticket_number}
                placeholder="Search ticket number"
                onChange={(ticket_number) => onChange({ ticket_number })}
              />
            </div>

            <div className="filter-more-field filter-more-field-wide">
              <label>Service Start Date</label>
              <div className="filter-more-date-range">
                <input
                  type="date"
                  value={time_start_from ?? ""}
                  max={time_start_to || undefined}
                  onChange={(e) =>
                    onChange({ time_start_from: e.target.value || undefined })
                  }
                />
                <span className="filter-more-date-sep">to</span>
                <input
                  type="date"
                  value={time_start_to ?? ""}
                  min={time_start_from || undefined}
                  onChange={(e) =>
                    onChange({ time_start_to: e.target.value || undefined })
                  }
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
