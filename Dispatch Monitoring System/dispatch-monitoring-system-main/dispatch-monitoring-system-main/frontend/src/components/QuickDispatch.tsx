import { useState } from "react";
import type { MonitoringRecord } from "../lib/types";
import TechnicianTeamSelector from "./TechnicianTeamSelector";

import "../styles/Forms.css";

function toLocalDatetimeValue(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export interface DispatchFormData {
  time_start: string | null;
  time_accomplish: string | null;
  teams: number[];
}

interface QuickDispatchProps {
  record: MonitoringRecord;
  onConfirm: (data: DispatchFormData) => void;
  onCancel: () => void;
  loading?: boolean;
}

export default function QuickDispatch({
  record,
  onConfirm,
  onCancel,
  loading,
}: QuickDispatchProps) {
  const [timeStart, setTimeStart] = useState(
    record.time_start ? toLocalDatetimeValue(record.time_start) : ""
  );
  const [teams, setTeams] = useState<number[]>(
    record.teams?.map((t) => t.technician.id) || []
  );
  const toggleTeam = (techId: number) => {
    setTeams((cur) =>
      cur.includes(techId) ? cur.filter((t) => t !== techId) : [...cur, techId]
    );
  };

  const toggleTeamMany = (techIds: number[], select: boolean) => {
    setTeams((cur) => {
      const set = new Set(cur);
      techIds.forEach((id) => (select ? set.add(id) : set.delete(id)));
      return [...set];
    });
  };

  const handleConfirm = () => {
    onConfirm({
      time_start: timeStart || null,
      time_accomplish: null,
      teams,
    });
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="form-modal">
          <div className="form-header">
            <h2>Dispatch — {record.client}</h2>
          </div>

          <div className="form-body">

            {/* ── Timing ── */}
            <div className="section-divider">
              <span className="section-divider-label">Timing</span>
            </div>
            <div className="form-row">
              <label>Start Time</label>
              <input
                type="datetime-local"
                value={timeStart}
                onChange={(e) => setTimeStart(e.target.value)}
              />
            </div>

            {/* ── Team Assignment ── */}
            <div className="section-divider">
              <span className="section-divider-label">Team Assignment</span>
            </div>
            <div className="form-row">
              <TechnicianTeamSelector
                selected={teams}
                onToggle={toggleTeam}
                onToggleMany={toggleTeamMany}
                idPrefix="dispatch-modal-tech"
              />
            </div>

          </div>

          <div className="form-footer dispatch-footer">
            <button type="button" className="btn-cancel" onClick={onCancel} disabled={loading}>
              Cancel
            </button>
            <button
              type="button"
              className="btn-submit"
              onClick={handleConfirm}
              disabled={loading || !timeStart}
            >
              {loading ? "Dispatching..." : "Dispatch"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
