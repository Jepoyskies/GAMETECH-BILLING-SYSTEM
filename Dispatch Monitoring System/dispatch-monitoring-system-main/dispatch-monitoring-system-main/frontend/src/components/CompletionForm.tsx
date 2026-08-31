import { useState, useRef } from "react";
import { useToast } from "../context/ToastContext";
import type { MonitoringRecord } from "../lib/types";
import SlideToConfirm, { type SlideToConfirmHandle } from "./SlideToConfirm";
import TechnicianTeamSelector from "./TechnicianTeamSelector";
import "../styles/Forms.css";

function toLocalDatetimeValue(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export interface CompletionFormData {
  time_start: string | null;
  time_accomplish: string | null;
  teams: number[];
  nap_port: string;
  cable_length: string;
  nap_reading: string;
  pole_number: string;
  plan_package: string;
  ont_modem_sn: string;
  signal_level: string;
  facility: string;
  house_reading: string;
  special_instruction: string;
  technician_remarks: string;
  acknowledged_by: string;
  actions_taken: string;
}

interface CompletionFormProps {
  record: MonitoringRecord;
  onConfirm: (data: CompletionFormData) => void;
  onCancel: () => void;
  loading?: boolean;
}

export default function CompletionForm({
  record,
  onConfirm,
  onCancel,
  loading,
}: CompletionFormProps) {
  const { addToast } = useToast();
  const slideRef = useRef<SlideToConfirmHandle>(null);

  const [timeStart, setTimeStart] = useState(
    record.time_start ? toLocalDatetimeValue(record.time_start) : ""
  );
  const [timeAccomplish, setTimeAccomplish] = useState(
    record.time_accomplish ? toLocalDatetimeValue(record.time_accomplish) : ""
  );
  const [teams, setTeams] = useState<number[]>(
    record.teams?.map((t) => t.technician.id) || []
  );
  const [napPort, setNapPort] = useState("");
  const [cableLength, setCableLength] = useState("");
  const [napReading, setNapReading] = useState("");
  const [poleNumber, setPoleNumber] = useState("");
  const [planPackage, setPlanPackage] = useState("");
  const [ontModemSn, setOntModemSn] = useState("");
  const [signalLevel, setSignalLevel] = useState("");
  const [facility, setFacility] = useState("");
  const [houseReading, setHouseReading] = useState("");
  const [specialInstruction, setSpecialInstruction] = useState("");
  const [technicianRemarks, setTechnicianRemarks] = useState("");
  const [acknowledgedBy, setAcknowledgedBy] = useState("");
  const [actionsTaken, setActionsTaken] = useState("");

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
    if (!timeAccomplish) {
      addToast("End time is required to mark as done.", "error");
      slideRef.current?.reset();
      return;
    }
    if (timeStart && timeAccomplish && new Date(timeAccomplish) < new Date(timeStart)) {
      addToast("End time cannot be earlier than start time.", "error");
      slideRef.current?.reset();
      return;
    }

    onConfirm({
      time_start: timeStart || null,
      time_accomplish: timeAccomplish || null,
      teams,
      nap_port: napPort,
      cable_length: cableLength,
      nap_reading: napReading,
      pole_number: poleNumber,
      plan_package: planPackage,
      ont_modem_sn: ontModemSn,
      signal_level: signalLevel,
      facility,
      house_reading: houseReading,
      special_instruction: specialInstruction,
      technician_remarks: technicianRemarks,
      acknowledged_by: acknowledgedBy,
      actions_taken: actionsTaken,
    });
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="form-modal">
          <div className="form-header">
            <h2>Mark as Done — {record.client}</h2>
          </div>

          <div className="form-body">

            {/* ── Work Timeline ── */}
            <div className="section-divider">
              <span className="section-divider-label">Work Timeline</span>
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>Date Started</label>
                <input
                  type="datetime-local"
                  value={timeStart}
                  onChange={(e) => setTimeStart(e.target.value)}
                />
              </div>
              <div className="form-row">
                <label>Date Finished *</label>
                <input
                  type="datetime-local"
                  value={timeAccomplish}
                  onChange={(e) => setTimeAccomplish(e.target.value)}
                  required
                />
              </div>
            </div>

            {/* ── Service Details ── */}
            <div className="section-divider">
              <span className="section-divider-label">Service Details</span>
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>NAP/Port</label>
                <input type="text" value={napPort} onChange={(e) => setNapPort(e.target.value)} />
              </div>
              <div className="form-row">
                <label>NAP Reading</label>
                <input type="text" value={napReading} onChange={(e) => setNapReading(e.target.value)} />
              </div>
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>House Reading</label>
                <input type="text" value={houseReading} onChange={(e) => setHouseReading(e.target.value)} />
              </div>
              <div className="form-row">
                <label>Pole Number</label>
                <input type="text" value={poleNumber} onChange={(e) => setPoleNumber(e.target.value)} />
              </div>
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>Cable Length Used</label>
                <input type="text" value={cableLength} onChange={(e) => setCableLength(e.target.value)} />
              </div>
              <div className="form-row">
                <label>Signal Level</label>
                <input type="text" value={signalLevel} onChange={(e) => setSignalLevel(e.target.value)} />
              </div>
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>Facility</label>
                <input type="text" value={facility} onChange={(e) => setFacility(e.target.value)} />
              </div>
              <div className="form-row">
                <label>ONT/Modem SN</label>
                <input type="text" value={ontModemSn} onChange={(e) => setOntModemSn(e.target.value)} />
              </div>
            </div>
            <div className="form-row">
              <label>Plan/Package</label>
              <input type="text" value={planPackage} onChange={(e) => setPlanPackage(e.target.value)} />
            </div>

            {/* ── Sign-off ── */}
            <div className="section-divider">
              <span className="section-divider-label">Sign-off</span>
            </div>
            <div className="form-row">
              <label>Actions Taken</label>
              <textarea value={actionsTaken} onChange={(e) => setActionsTaken(e.target.value)} rows={2} />
            </div>
            <div className="form-row">
              <label>Special Instruction</label>
              <textarea value={specialInstruction} onChange={(e) => setSpecialInstruction(e.target.value)} rows={2} />
            </div>
            <div className="form-row">
              <label>Technician Remarks</label>
              <textarea value={technicianRemarks} onChange={(e) => setTechnicianRemarks(e.target.value)} rows={2} />
            </div>
            <div className="form-row">
              <label>Acknowledged By</label>
              <input type="text" value={acknowledgedBy} onChange={(e) => setAcknowledgedBy(e.target.value)} />
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
                idPrefix="completion-modal-tech"
              />
            </div>
          </div>

          <div className="form-footer dispatch-footer">
            <button type="button" className="btn-cancel" onClick={onCancel} disabled={loading}>
              Cancel
            </button>
            <SlideToConfirm
              ref={slideRef}
              label="Slide to Mark Done"
              confirmedLabel={loading ? "Saving..." : "Done!"}
              onConfirm={handleConfirm}
              disabled={!timeStart}
              loading={loading}
            />
          </div>
        </div>
      </div>
    </div>
  );
}