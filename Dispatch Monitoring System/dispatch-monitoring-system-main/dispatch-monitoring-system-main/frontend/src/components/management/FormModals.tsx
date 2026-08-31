import { useState, type FormEvent } from "react";
import { Eye, EyeOff } from "lucide-react";
import type { CSR, Technician, Team } from "../../lib/types";
import { type MonthlyTarget } from "../../hooks/useDashboard";
import { MONTHS } from "../../lib/constants";
import "../../styles/Teams.css";

interface AccountFormModalProps {
  isOpen: boolean;
  editCSR: CSR | null;
  onClose: () => void;
  onSubmit: (e: FormEvent) => void;
  name: string;
  setName: (v: string) => void;
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  retypePassword: string;
  setRetypePassword: (v: string) => void;
  currentPassword: string;
  setCurrentPassword: (v: string) => void;
  saving: boolean;
  onUpdatePassword?: () => void;
  updatePasswordLoading?: boolean;
  requireCurrentPw?: boolean;
}

export function AccountFormModal({
  isOpen,
  editCSR,
  onClose,
  onSubmit,
  name,
  setName,
  email,
  setEmail,
  password,
  setPassword,
  retypePassword,
  setRetypePassword,
  currentPassword,
  setCurrentPassword,
  saving,
  onUpdatePassword,
  updatePasswordLoading,
  requireCurrentPw,
}: AccountFormModalProps) {
  if (!isOpen) return null;

  const isEditing = !!editCSR;
  const [showPassword, setShowPassword] = useState(false);
  const [showRetype, setShowRetype] = useState(false);
  const [showCurrent, setShowCurrent] = useState(false);

  return (
    <div className="modal-overlay">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <form className="form-modal" onSubmit={onSubmit}>
          <div className="form-header">
            <h2>{isEditing ? "Edit Account" : "Add Account"}</h2>
          </div>
          <div className="form-body">
            <div className="form-row">
              <label>Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter full name"
                disabled={saving}
              />
            </div>
            <div className="form-row">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                autoComplete="email"
                disabled={saving}
              />
            </div>
            {!isEditing && (
              <>
                <div className="form-row">
                  <label>Temporary Password for CSR</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    autoComplete="new-password"
                    disabled={saving}
                  />
                </div>
                <div className="form-row">
                  <label>Confirm with your password</label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Your SUPERADMIN password"
                    autoComplete="current-password"
                    disabled={saving}
                  />
                </div>
                <p className="period-meta">
                  New accounts are created as CSR Admin. The new user can
                  sign in with this email and password.
                </p>
              </>
            )}
            {isEditing && onUpdatePassword && (
              <div className="form-section danger">
                <p className="form-section-title">Change Password</p>
                {requireCurrentPw && (
                  <div className="form-row">
                    <label>Current Password</label>
                    <div className="password-input-wrapper">
                      <input
                        type={showCurrent ? "text" : "password"}
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        placeholder="Enter current password"
                        autoComplete="current-password"
                        disabled={updatePasswordLoading}
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowCurrent(!showCurrent)}
                        tabIndex={-1}
                      >
                        {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                )}
                <div className="form-row">
                  <label>New Password</label>
                  <div className="password-input-wrapper">
                    <input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="At least 8 characters"
                      autoComplete="new-password"
                      disabled={updatePasswordLoading}
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
                <div className="form-row">
                  <label>Retype Password</label>
                  <div className="password-input-wrapper">
                    <input
                      type={showRetype ? "text" : "password"}
                      value={retypePassword}
                      onChange={(e) => setRetypePassword(e.target.value)}
                      placeholder="Re-enter password"
                      autoComplete="new-password"
                      disabled={updatePasswordLoading}
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      onClick={() => setShowRetype(!showRetype)}
                      tabIndex={-1}
                    >
                      {showRetype ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-submit"
                  onClick={onUpdatePassword}
                  disabled={updatePasswordLoading || password.length < 8 || password !== retypePassword}
                >
                  {updatePasswordLoading ? "Updating..." : "Update Password"}
                </button>
              </div>
            )}
          </div>
          <div className="form-footer">
            <button type="button" className="btn-cancel" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn-submit" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface DeleteConfirmModalProps {
  isOpen: boolean;
  targetName?: string;
  targetLabel: string;
  confirmName?: string;
  setConfirmName?: (v: string) => void;
  message?: string;
  onClose: () => void;
  onSubmit: (e: FormEvent) => void;
  saving: boolean;
  danger?: boolean;
}

export function DeleteConfirmModal({
  isOpen,
  targetName,
  targetLabel,
  confirmName,
  setConfirmName,
  message,
  onClose,
  onSubmit,
  saving,
  danger,
}: DeleteConfirmModalProps) {
  if (!isOpen) return null;
  const needsConfirm = confirmName !== undefined && setConfirmName !== undefined;

  return (
    <div className="modal-overlay">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <form className={`form-modal${danger ? " danger" : ""}`} onSubmit={onSubmit}>
          <div className="form-header">
            <h2>Delete {targetLabel}</h2>
          </div>
          <div className="form-body">
            {needsConfirm ? (
              <>
                <p className="delete-warning">
                  This will remove <strong>{targetName}</strong> from the system.
                  Existing records linked to this {targetLabel.toLowerCase()} will be kept.
                </p>
                <div className="form-row">
                  <label>Type the {targetLabel.toLowerCase()} name to confirm</label>
                  <input
                    type="text"
                    value={confirmName}
                    onChange={(e) => setConfirmName(e.target.value)}
                    placeholder={targetName}
                    disabled={saving}
                    autoFocus
                  />
                </div>
              </>
            ) : (
              <p className="delete-warning">{message ?? `Are you sure you want to delete this ${targetLabel.toLowerCase()}?`}</p>
            )}
          </div>
          <div className="form-footer">
            <button type="button" className="btn-cancel" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn-delete-submit"
              disabled={saving || (needsConfirm && confirmName.trim() !== targetName)}
            >
              {saving ? "Deleting..." : `Delete ${targetLabel}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface TechnicianFormModalProps {
  isOpen: boolean;
  editTech: Technician | null;
  onClose: () => void;
  onSubmit: (e: FormEvent) => void;
  name: string;
  setName: (v: string) => void;
  contactNumber: string;
  setContactNumber: (v: string) => void;
  targetDay: string;
  setTargetDay: (v: string) => void;
  targetMonth: string;
  setTargetMonth: (v: string) => void;
  saving: boolean;
}

export function TechnicianFormModal({
  isOpen,
  editTech,
  onClose,
  onSubmit,
  name,
  setName,
  contactNumber,
  setContactNumber,
  targetDay,
  setTargetDay,
  targetMonth,
  setTargetMonth,
  saving,
}: TechnicianFormModalProps) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <form className="form-modal" onSubmit={onSubmit}>
          <div className="form-header">
            <h2>{editTech ? "Edit Technician" : "Add Technician"}</h2>
          </div>
          <div className="form-body">
            <div className="form-row">
              <label>Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter technician name"
                disabled={saving}
                autoFocus
              />
            </div>
            <div className="form-row">
              <label>Contact Number</label>
              <input
                type="text"
                value={contactNumber}
                onChange={(e) => setContactNumber(e.target.value)}
                placeholder="Enter contact number (optional)"
                disabled={saving}
              />
            </div>
            <div className="form-row-group">
              <div className="form-row">
                <label>Target per Day</label>
                <input
                  type="number"
                  value={targetDay}
                  onChange={(e) => setTargetDay(e.target.value)}
                  placeholder="0"
                  min="0"
                  disabled={saving}
                />
              </div>
              <div className="form-row">
                <label>Target per Month</label>
                <input
                  type="number"
                  value={targetMonth}
                  onChange={(e) => setTargetMonth(e.target.value)}
                  placeholder="0"
                  min="0"
                  disabled={saving}
                />
              </div>
            </div>
          </div>
          <div className="form-footer">
            <button type="button" className="btn-cancel" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn-submit" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface TeamFormModalProps {
  isOpen: boolean;
  editTeam: Team | null;
  onClose: () => void;
  onSubmit: (e: FormEvent) => void;
  name: string;
  setName: (v: string) => void;
  saving: boolean;
  unassignedTechnicians?: Technician[];
  selectedMemberIds?: number[];
  onSelectedMembersChange?: (ids: number[]) => void;
}

export function TeamFormModal({
  isOpen,
  editTeam,
  onClose,
  onSubmit,
  name,
  setName,
  saving,
  unassignedTechnicians = [],
  selectedMemberIds = [],
  onSelectedMembersChange,
}: TeamFormModalProps) {
  if (!isOpen) return null;

  const toggleMember = (id: number) => {
    if (!onSelectedMembersChange) return;
    const next = selectedMemberIds.includes(id)
      ? selectedMemberIds.filter((v) => v !== id)
      : [...selectedMemberIds, id];
    onSelectedMembersChange(next);
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <form className="form-modal" onSubmit={onSubmit}>
          <div className="form-header">
            <h2>{editTeam ? "Rename Team" : "Create Team"}</h2>
          </div>
          <div className="form-body">
            <div className="form-row">
              <label>Team Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Team 1"
                disabled={saving}
                autoFocus
              />
            </div>

            {!editTeam && unassignedTechnicians.length > 0 && (
              <>
                <div className="section-divider">
                  <span className="section-divider-label">Add Members</span>
                </div>
                <div className="team-member-picker">
                  {unassignedTechnicians.map((t) => (
                    <label key={t.id} className="team-member-picker-row">
                      <input
                        type="checkbox"
                        checked={selectedMemberIds.includes(t.id)}
                        onChange={() => toggleMember(t.id)}
                        disabled={saving}
                      />
                      <div className="team-member-picker-info">
                        <span className="team-member-picker-name">{t.name}</span>
                        <span className="team-member-picker-meta">{t.target_per_day}/day · {t.target_per_month}/mo</span>
                      </div>
                    </label>
                  ))}
                </div>
              </>
            )}
          </div>
          <div className="form-footer">
            <button type="button" className="btn-cancel" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn-submit" disabled={saving}>
              {saving ? "Saving..." : editTeam ? "Rename" : "Create Team"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface TargetFormModalProps {
  isOpen: boolean;
  editTarget: MonthlyTarget | null;
  onClose: () => void;
  onSubmit: (e: FormEvent) => void;
  month: number;
  setMonth: (v: number) => void;
  year: number;
  setYear: (v: number) => void;
  value: string;
  setValue: (v: string) => void;
  saving: boolean;
}

export function TargetFormModal({
  isOpen,
  editTarget,
  onClose,
  onSubmit,
  month,
  setMonth,
  year,
  setYear,
  value,
  setValue,
  saving,
}: TargetFormModalProps) {
  if (!isOpen) return null;

  const now = new Date();
  const targetYearOptions = (() => {
    const current = now.getFullYear();
    const years: number[] = [];
    for (let y = current - 3; y <= current + 2; y++) years.push(y);
    if (!years.includes(year)) years.push(year);
    return years.sort((a, b) => a - b);
  })();

  return (
    <div className="modal-overlay">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <form className="form-modal" onSubmit={onSubmit}>
          <div className="form-header">
            <h2>{editTarget ? "Edit Target" : "Set Target"}</h2>
          </div>
          <div className="form-body">
            <div className="form-row-group">
              <div className="form-row">
                <label>Month</label>
                <select
                  value={month}
                  onChange={(e) => setMonth(Number(e.target.value))}
                  disabled={saving || !!editTarget}
                >
                  {MONTHS.map((m) => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-row">
                <label>Year</label>
                <select
                  value={year}
                  onChange={(e) => setYear(Number(e.target.value))}
                  disabled={saving || !!editTarget}
                >
                  {targetYearOptions.map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-row">
              <label>Target Installations</label>
              <input
                type="number"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="e.g. 120"
                min="0"
                disabled={saving}
              />
            </div>
          </div>
          <div className="form-footer">
            <button type="button" className="btn-cancel" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn-submit" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}