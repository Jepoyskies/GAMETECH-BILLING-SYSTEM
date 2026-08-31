import { useEffect, useMemo, useRef, useState } from "react";
import { useTechnicians } from "../../hooks/useTechnician";
import "../../styles/Filters.css";

interface TeamMultiselectFilterProps {
  value?: number[];
  onChange: (teamIds: number[] | undefined) => void;
}

export default function TeamMultiselectFilter({
  value = [],
  onChange,
}: TeamMultiselectFilterProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const { data: technicians } = useTechnicians();

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

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return technicians;
    return technicians.filter((t) => t.name.toLowerCase().includes(q));
  }, [technicians, search]);

  const toggle = (id: number) => {
    const next = value.includes(id)
      ? value.filter((v) => v !== id)
      : [...value, id];
    onChange(next.length > 0 ? next : undefined);
  };

  const label =
    value.length === 0
      ? "Team"
      : value.length === 1
        ? technicians.find((t) => t.id === value[0])?.name ?? "1 team"
        : `${value.length} teams`;

  return (
    <div className="filter-team-select" ref={containerRef}>
      <button
        type="button"
        className={`filter-team-btn${open ? " active" : ""}`}
        onClick={() => setOpen((v) => !v)}
      >
        {label}
      </button>

      {open && (
        <div className="filter-popover filter-team-popover">
          <input
            type="text"
            className="filter-team-search"
            placeholder="Search team..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="filter-team-list">
            {filtered.length === 0 ? (
              <div className="filter-team-empty">No technicians found</div>
            ) : (
              filtered.map((tech) => (
                <label key={tech.id} className="filter-team-option">
                  <input
                    type="checkbox"
                    checked={value.includes(tech.id)}
                    onChange={() => toggle(tech.id)}
                  />
                  {tech.name}
                </label>
              ))
            )}
          </div>
          {value.length > 0 && (
            <div className="filter-popover-actions">
              <button
                type="button"
                className="filter-popover-clear"
                onClick={() => onChange(undefined)}
              >
                Clear
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
