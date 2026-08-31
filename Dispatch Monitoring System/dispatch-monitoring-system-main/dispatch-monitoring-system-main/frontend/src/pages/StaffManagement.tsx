import { useEffect, useState } from "react";
import { AlertCircle, Pen, Settings, Trash2 } from "lucide-react";
import { useCSR } from "../hooks/useCSR";
import { useAccounts } from "../hooks/useAccounts";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useTechnicians } from "../hooks/useTechnician";
import { useTeams } from "../hooks/useTeams";
import { useManageTargets, type MonthlyTarget } from "../hooks/useDashboard";
import type { CSR, Technician, Team } from "../lib/types";
import DataTable from "../components/DataTable";
import ConfigurableListEditor from "../components/management/ConfigurableListEditor";
import PdfViewer from "../components/PdfViewer";
import {
  AccountFormModal,
  DeleteConfirmModal,
  TechnicianFormModal,
  TeamFormModal,
  TargetFormModal,
} from "../components/management/FormModals";
import "../styles/ListPage.css";
import "../styles/Forms.css";
import "../styles/Teams.css";

export default function StaffManagement() {
  const { user, isSuperAdmin } = useAuth();
  const { addToast } = useToast();
  const { data: csrs, loading: csrLoading, error: csrError, createAccount, updateAccount, updatePassword, refetch: refetchAccounts } = useAccounts();
  const { deleteCSR } = useCSR();
  const { data: technicians, loading: techLoading, error: techError, createTechnician, updateTechnician, deleteTechnician } = useTechnicians();
  const { data: teams, loading: teamLoading, error: teamError, createTeam, updateTeam, deleteTeam } = useTeams();
  const { data: targets, loading: targetLoading, error: targetError, upsertTarget, deleteTarget } = useManageTargets();

  useEffect(() => { if (csrError) addToast(csrError, "error"); }, [csrError]);
  useEffect(() => { if (techError) addToast(techError, "error"); }, [techError]);
  useEffect(() => { if (teamError) addToast(teamError, "error"); }, [teamError]);
  useEffect(() => { if (targetError) addToast(targetError, "error"); }, [targetError]);

  const [activeTab, setActiveTab] = useState<"csr" | "teams" | "target" | "dropdownOptions">("csr");
  const [manualOpen, setManualOpen] = useState(false);

  // CSR state
  const [showCSRForm, setShowCSRForm] = useState(false);
  const [editCSR, setEditCSR] = useState<CSR | null>(null);
  const [csrName, setCsrName] = useState("");
  const [csrEmail, setCsrEmail] = useState("");
  const [csrPassword, setCsrPassword] = useState("");
  const [csrRetypePassword, setCsrRetypePassword] = useState("");
  const [csrCurrentPassword, setCsrCurrentPassword] = useState("");
  const [csrSaving, setCsrSaving] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [deleteCSRTarget, setDeleteCSRTarget] = useState<CSR | null>(null);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [deleteSaving, setDeleteSaving] = useState(false);

  // Technician state
  const [showTechForm, setShowTechForm] = useState(false);
  const [editTech, setEditTech] = useState<Technician | null>(null);
  const [techName, setTechName] = useState("");
  const [techContactNumber, setTechContactNumber] = useState("");
  const [techTargetDay, setTechTargetDay] = useState("");
  const [techTargetMonth, setTechTargetMonth] = useState("");
  const [techSaving, setTechSaving] = useState(false);
  const [deleteTechTarget, setDeleteTechTarget] = useState<Technician | null>(null);
  const [deleteTechConfirmName, setDeleteTechConfirmName] = useState("");
  const [deleteTechSaving, setDeleteTechSaving] = useState(false);

  // Team state
  const [showTeamForm, setShowTeamForm] = useState(false);
  const [editTeam, setEditTeam] = useState<Team | null>(null);
  const [teamName, setTeamName] = useState("");
  const [teamSaving, setTeamSaving] = useState(false);
  const [selectedTeamMembers, setSelectedTeamMembers] = useState<number[]>([]);
  const [deleteTeamTarget, setDeleteTeamTarget] = useState<Team | null>(null);
  const [deleteTeamSaving, setDeleteTeamSaving] = useState(false);

  // Target state
  const [deleteTargetModal, setDeleteTargetModal] = useState<MonthlyTarget | null>(null);
  const [deleteTargetSaving, setDeleteTargetSaving] = useState(false);
  const [addMemberTeamId, setAddMemberTeamId] = useState<number | null>(null);
  const [addMemberTechId, setAddMemberTechId] = useState<string>("");
  const [memberSaving, setMemberSaving] = useState(false);

  // Target state
  const [showTargetForm, setShowTargetForm] = useState(false);
  const [editTarget, setEditTarget] = useState<MonthlyTarget | null>(null);
  const now = new Date();
  const [targetMonth, setTargetMonth] = useState(now.getMonth() + 1);
  const [targetYear, setTargetYear] = useState(now.getFullYear());
  const [targetValue, setTargetValue] = useState("");
  const [targetSaving, setTargetSaving] = useState(false);

  // CSR handlers
  const resetCSRForm = () => {
    setCsrName("");
    setCsrEmail("");
    setCsrPassword("");
    setCsrRetypePassword("");
    setCsrCurrentPassword("");
    setEditCSR(null);
  };

  const handleNewCSR = () => {
    resetCSRForm();
    setShowCSRForm(true);
  };

  const handleEditCSR = (csr: CSR) => {
    const isOwn = user?.id === csr.id;
    if (!isSuperAdmin && !isOwn) return;
    resetCSRForm();
    setEditCSR(csr);
    setCsrName(csr.name);
    setCsrEmail(csr.email ?? "");
    setShowCSRForm(true);
  };

  const handleCSRSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csrName.trim()) {
      addToast("Name is required", "error");
      return;
    }
    if (!csrEmail.trim()) {
      addToast("Email is required", "error");
      return;
    }
    if (!editCSR) {
      if (csrPassword.length < 8) { addToast("Password must be at least 8 characters", "error"); return; }
      if (!csrCurrentPassword) { addToast("Enter your password to confirm", "error"); return; }
    }
    try {
      setCsrSaving(true);
      if (editCSR) {
        await updateAccount(editCSR.id, {
          name: csrName.trim(),
          email: csrEmail.trim(),
        });
      } else {
        await createAccount({
          name: csrName.trim(),
          email: csrEmail.trim(),
          password: csrPassword,
          current_password: csrCurrentPassword,
        });
      }
      addToast(editCSR ? "Account updated successfully" : "Account created successfully", "success");
      refetchAccounts();
      setShowCSRForm(false);
      resetCSRForm();
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to save", "error");
    } finally {
      setCsrSaving(false);
    }
  };

  const handleDeleteCSR = (csr: CSR) => {
    if (!isSuperAdmin) return;
    setDeleteCSRTarget(csr);
    setDeleteConfirmName("");
  };

  const handleConfirmDeleteCSR = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deleteCSRTarget) return;
    try {
      setDeleteSaving(true);
      await deleteCSR(deleteCSRTarget.id, deleteConfirmName.trim());
      addToast("Account deleted successfully", "success");
      setDeleteCSRTarget(null);
      setDeleteConfirmName("");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to delete", "error");
    } finally {
      setDeleteSaving(false);
    }
  };

  const handleUpdatePassword = async () => {
    if (!editCSR || csrPassword.length < 8) return;
    if (csrPassword !== csrRetypePassword) {
      addToast("Passwords do not match", "error");
      return;
    }
    const isOwn = user?.id === editCSR.id;
    if (!isSuperAdmin && !isOwn) return;
    try {
      setPasswordSaving(true);
      await updatePassword(editCSR.id, csrPassword, isOwn ? csrCurrentPassword : undefined);
      setCsrPassword("");
      setCsrRetypePassword("");
      setCsrCurrentPassword("");
      addToast("Password updated successfully", "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to update password", "error");
    } finally {
      setPasswordSaving(false);
    }
  };

  // Technician handlers
  const handleNewTech = () => {
    setEditTech(null);
    setTechName("");
    setTechContactNumber("");
    setTechTargetDay("");
    setTechTargetMonth("");
    setShowTechForm(true);
  };

  const handleEditTech = (tech: Technician) => {
    setEditTech(tech);
    setTechName(tech.name);
    setTechContactNumber(tech.contact_number || "");
    setTechTargetDay(String(tech.target_per_day));
    setTechTargetMonth(String(tech.target_per_month));
    setShowTechForm(true);
  };

  const handleTechSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!techName.trim()) {
      addToast("Name is required", "error");
      return;
    }
    try {
      setTechSaving(true);
      const body: {
        name: string;
        contact_number?: string | null;
        target_per_day: number;
        target_per_month: number;
      } = {
        name: techName.trim(),
        target_per_day: techTargetDay ? parseInt(techTargetDay, 10) : 0,
        target_per_month: techTargetMonth ? parseInt(techTargetMonth, 10) : 0,
      };
      if (techContactNumber.trim()) {
        body.contact_number = techContactNumber.trim();
      }
      if (editTech) {
        await updateTechnician(editTech.id, body);
        addToast("Technician updated successfully", "success");
      } else {
        await createTechnician(body);
        addToast("Technician created successfully", "success");
      }
      setShowTechForm(false);
      setTechName("");
      setTechContactNumber("");
      setTechTargetDay("");
      setTechTargetMonth("");
      setEditTech(null);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to save", "error");
    } finally {
      setTechSaving(false);
    }
  };

  const handleDeleteTech = (tech: Technician) => {
    setDeleteTechTarget(tech);
    setDeleteTechConfirmName("");
  };

  const handleConfirmDeleteTech = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deleteTechTarget) return;
    try {
      setDeleteTechSaving(true);
      await deleteTechnician(deleteTechTarget.id, deleteTechConfirmName.trim());
      addToast("Technician deleted successfully", "success");
      setDeleteTechTarget(null);
      setDeleteTechConfirmName("");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to delete", "error");
    } finally {
      setDeleteTechSaving(false);
    }
  };

  // Team handlers
  const handleNewTeam = () => {
    setEditTeam(null);
    setTeamName("");
    setSelectedTeamMembers([]);
    setShowTeamForm(true);
  };

  const handleEditTeam = (team: Team) => {
    setEditTeam(team);
    setTeamName(team.name);
    setShowTeamForm(true);
  };

  const handleTeamSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!teamName.trim()) {
      addToast("Team name is required", "error");
      return;
    }
    try {
      setTeamSaving(true);
      if (editTeam) {
        await updateTeam(editTeam.id, { name: teamName.trim() });
        addToast("Team updated successfully", "success");
      } else {
        const newTeam = await createTeam({ name: teamName.trim() });
        if (selectedTeamMembers.length > 0) {
          await Promise.all(
            selectedTeamMembers.map((techId) =>
              updateTechnician(techId, { team_id: newTeam.id })
            )
          );
        }
        addToast("Team created successfully", "success");
      }
      setShowTeamForm(false);
      setEditTeam(null);
      setTeamName("");
      setSelectedTeamMembers([]);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to save", "error");
    } finally {
      setTeamSaving(false);
    }
  };

  const handleDeleteTeam = async (team: Team) => {
    setDeleteTeamTarget(team);
  };

  const handleConfirmDeleteTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deleteTeamTarget) return;
    setDeleteTeamSaving(true);
    try {
      await deleteTeam(deleteTeamTarget.id);
      addToast("Team deleted successfully", "success");
      setDeleteTeamTarget(null);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to delete", "error");
    } finally {
      setDeleteTeamSaving(false);
    }
  };

  const handleAddMember = async (teamId: number) => {
    if (!addMemberTechId) return;
    try {
      setMemberSaving(true);
      await updateTechnician(parseInt(addMemberTechId, 10), { team_id: teamId });
      addToast("Member added successfully", "success");
      setAddMemberTechId("");
      setAddMemberTeamId(null);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to add member", "error");
    } finally {
      setMemberSaving(false);
    }
  };

  const handleRemoveMember = async (techId: number) => {
    try {
      await updateTechnician(techId, { team_id: null });
      addToast("Member removed successfully", "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to remove member", "error");
    }
  };

  // Target handlers
  const handleNewTarget = () => {
    setEditTarget(null);
    setTargetMonth(now.getMonth() + 1);
    setTargetYear(now.getFullYear());
    setTargetValue("");
    setShowTargetForm(true);
  };

  const handleEditTarget = (target: MonthlyTarget) => {
    setEditTarget(target);
    setTargetMonth(target.month);
    setTargetYear(target.year);
    setTargetValue(String(target.target));
    setShowTargetForm(true);
  };

  const handleTargetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = parseInt(targetValue, 10);
    if (isNaN(value) || value < 0) {
      addToast("Target must be a non-negative number", "error");
      return;
    }
    try {
      setTargetSaving(true);
      await upsertTarget(targetMonth, targetYear, value);
      addToast("Target saved successfully", "success");
      setShowTargetForm(false);
      setEditTarget(null);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to save", "error");
    } finally {
      setTargetSaving(false);
    }
  };

  const handleDeleteTarget = async (target: MonthlyTarget) => {
    setDeleteTargetModal(target);
  };

  const handleConfirmDeleteTarget = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deleteTargetModal) return;
    setDeleteTargetSaving(true);
    try {
      await deleteTarget(deleteTargetModal.id);
      addToast("Target deleted successfully", "success");
      setDeleteTargetModal(null);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to delete", "error");
    } finally {
      setDeleteTargetSaving(false);
    }
  };

  // Columns for Staff Accounts (DO NOT DELETE)
  const csrColumns = [
    {
      key: "id",
      header: "ID",
      width: "80px",
      render: (row: CSR) => (
        <span className="row-badge badge-gray">
          {row.id}
        </span>
      ),
    },
    { key: "name", header: "Name", width: "400px"  },
    { key: "email", header: "Email", render: (row: CSR) => row.email ?? "—" },
    {
      key: "role",
      header: "Role",
      render: (row: CSR) => {
        const roleMap: Record<string, { label: string; color: string }> = {
          SUPERADMIN: { label: "Super Admin", color: "#dc2626" },
          CSR_ADMIN: { label: "CSR Admin", color: "#2563eb" },
        };
        const role = row.role ? roleMap[row.role] : undefined;
        if (!role) return "—";
        return (
          <span className={`row-badge ${row.role === "SUPERADMIN" ? "badge-red" : "badge-blue"}`}>
            {role.label}
          </span>
        );
      },
    },
    {
      key: "created_at",
      header: "Created At",
      render: (row: CSR) => new Date(row.created_at).toLocaleDateString(),
    },
    ...(isSuperAdmin || user
      ? [{
          key: "actions",
          header: "Actions",
          render: (row: CSR) => {
            const isOwn = user?.id === row.id;
            if (!isSuperAdmin && !isOwn) return null;
            return (
              <div className="row-actions">
                <button className="btn-edit" title="Edit" onClick={(e) => { e.stopPropagation(); handleEditCSR(row); }}><Pen size={14} /></button>
                {isSuperAdmin && row.role !== "SUPERADMIN" && (
                  <button className="btn-delete" title="Delete" onClick={(e) => { e.stopPropagation(); handleDeleteCSR(row); }}><Trash2 size={14} /></button>
                )}
              </div>
            );
          },
        }]
      : []),
  ];

  const techColumns = [
    {
      key: "id",
      header: "ID",
      width: "80px",
      render: (row: Technician) => (
        <span className="row-badge badge-gray">
          {row.id}
        </span>
      ),
    },
    { key: "name", header: "Name", width: "400px" },
    { key: "contact_number", header: "Contact", width: "250px" },
    {
      key: "team",
      header: "Team",
      render: (row: Technician) => {
        const team = teams.find((t) => t.id === row.team_id);
        return team?.name ?? "—";
      },
    },
    { key: "target_per_day", header: "Target/Day" },
    { key: "target_per_month", header: "Target/Month" },
    {
      key: "created_at",
      header: "Created At",
      render: (row: Technician) => new Date(row.created_at).toLocaleDateString(),
    },
    {
      key: "actions",
      header: "Actions",
      render: (row: Technician) => (
        <div className="row-actions">
          <button className="btn-edit" title="Edit" onClick={(e) => { e.stopPropagation(); handleEditTech(row); }}><Pen size={14} /></button>
          <button className="btn-delete" title="Delete" onClick={(e) => { e.stopPropagation(); handleDeleteTech(row); }}><Trash2 size={14} /></button>
        </div>
      ),
    },
  ];

  const targetColumns = [
    { key: "month_label", header: "Month", render: (row: MonthlyTarget) => row.month_label },
    { key: "year", header: "Year" },
    { key: "target", header: "Target" },
    { key: "actual", header: "Actual" },
    { key: "remaining", header: "Remaining" },
    { key: "percentage", header: "Percentage", render: (row: MonthlyTarget) => `${row.percentage}%` },
    {
      key: "actions",
      header: "Actions",
      render: (row: MonthlyTarget) => (
        <div className="row-actions">
          <button className="btn-edit" title="Edit" onClick={(e) => { e.stopPropagation(); handleEditTarget(row); }}><Pen size={14} /></button>
          <button className="btn-delete" title="Delete" onClick={(e) => { e.stopPropagation(); handleDeleteTarget(row); }}><Trash2 size={14} /></button>
        </div>
      ),
    },
  ];

  return (
    <div className="list-page">
      {/* Manamegemnt Page does not have btn so i'll add this mt (marginTop: "0.150rem") Removed because of the new manual btn */}
      <div className="list-header" style={{ marginTop: "0rem" }}>
        <h1><Settings size={24} /> Management</h1>
        <button onClick={() => setManualOpen(true)} title="Manual" className="btn-manual">
          <AlertCircle size={22} />
        </button>
      </div>

      {/* Tab buttons */}
      <div className="tabs">
        <button className={`tab-btn ${activeTab === "csr" ? "active" : ""}`} onClick={() => setActiveTab("csr")}>Accounts</button>
        <button className={`tab-btn ${activeTab === "teams" ? "active" : ""}`} onClick={() => setActiveTab("teams")}>Teams & Technicians</button>
        <button className={`tab-btn ${activeTab === "target" ? "active" : ""}`} onClick={() => setActiveTab("target")}>Target Installment</button>
        <button className={`tab-btn ${activeTab === "dropdownOptions" ? "active" : ""}`} onClick={() => setActiveTab("dropdownOptions")}>Dropdown Options</button>
      </div>

        {/* ── ACCOUNTS TAB ── */}
        {activeTab === "csr" && (
          <div className="tab-content">
            <div className="list-header">
              <h1>Accounts</h1>
              {isSuperAdmin && <button className="btn-primary" onClick={handleNewCSR}>+ Add Account</button>}
            </div>
            
            <DataTable
              data={csrs}
              columns={csrColumns}
              loading={csrLoading}
                          getKey={(row) => row.id}
              emptyMessage="No accounts found"
            />
          </div>
        )}

        {/* ── TEAMS & TECHNICIANS TAB ── */}
        {activeTab === "teams" && (
          <div className="tab-content">
            <div className="list-header">
              <h1>Teams</h1>
              <button className="btn-primary" onClick={handleNewTeam}>+ Add Team</button>
            </div>
            {teamLoading && <p className="period-meta">Loading teams…</p>}
            {!teamLoading && teams.length === 0 && (
              <div className="teams-empty-state">
                <p className="period-meta">No teams yet. Create a team to start grouping technicians.</p>
              </div>
            )}
            <div className="team-cards">
              {teams.map((team) => {
                const members = technicians.filter((t) => t.team_id === team.id);
                const unassigned = technicians.filter((t) => t.team_id == null);
                const isAddingHere = addMemberTeamId === team.id;
                return (
                  <div className="team-card" key={team.id}>
                    <div className="team-card-header">
                      <div className="team-card-title">
                        <h3>{team.name}</h3>
                        <span className="team-badge">{members.length} member{members.length === 1 ? "" : "s"}</span>
                      </div>
                      <div className="row-actions">
                        <button className="btn-edit" title="Rename" onClick={() => handleEditTeam(team)}><Pen size={14} /></button>
                        <button className="btn-delete" title="Delete" onClick={() => handleDeleteTeam(team)}><Trash2 size={14} /></button>
                      </div>
                    </div>
                    <div className="team-card-body">
                      {members.length === 0 ? (
                        <p className="team-empty-hint">No members yet. Add technicians below.</p>
                      ) : (
                        <ul className="team-member-list">
                          {members.map((m) => (
                            <li key={m.id} className="team-member-item">
                              <div className="team-member-info">
                                <span className="team-member-name">{m.name}</span>
                                <span className="team-member-meta">{m.target_per_day}/day · {m.target_per_month}/mo</span>
                              </div>
                              <button className="btn-remove-member" onClick={() => handleRemoveMember(m.id)} title="Remove from team">✕</button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div className="team-card-footer">
                      {isAddingHere ? (
                        <div className="add-member-row">
                          <select value={addMemberTechId} onChange={(e) => setAddMemberTechId(e.target.value)} disabled={memberSaving} autoFocus>
                            <option value="">Select technician</option>
                            {unassigned.map((t) => (<option key={t.id} value={t.id}>{t.name}</option>))}
                          </select>
                          <button className="btn-submit-sm" onClick={() => handleAddMember(team.id)} disabled={memberSaving || !addMemberTechId}>
                            {memberSaving ? "Adding…" : "Add"}
                          </button>
                          <button className="btn-cancel-sm" onClick={() => { setAddMemberTeamId(null); setAddMemberTechId(""); }} disabled={memberSaving}>Cancel</button>
                        </div>
                      ) : (
                        <button
                          className="btn-add-member"
                          onClick={() => { setAddMemberTeamId(team.id); setAddMemberTechId(""); }}
                          disabled={unassigned.length === 0}
                          title={unassigned.length === 0 ? "All technicians are already in a team" : ""}
                        >
                          + Add Member
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* ── All Technicians ── */}
            <div className="all-technicians-section">
              <div className="list-header">
                <h2>All Technicians</h2>
                <button className="btn-primary" onClick={handleNewTech}>+ Add Technician</button>
              </div>
              <DataTable
                data={technicians}
                columns={techColumns}
                loading={techLoading}
                onRowClick={handleEditTech}
                getKey={(row) => row.id}
                emptyMessage="No technicians found"
              />
            </div>
          </div>
        )}

        {/* ── TARGET TAB ── */}
        {activeTab === "target" && (
          <div className="tab-content">
            <div className="list-header">
              <h1>Target Installment</h1>
              <button className="btn-primary" onClick={handleNewTarget}>+ Set Target</button>
            </div>
            
            <DataTable
              data={targets}
              columns={targetColumns}
              loading={targetLoading}
              onRowClick={handleEditTarget}
              getKey={(row) => row.id}
              emptyMessage="No installation targets configured yet"
            />
          </div>
        )}

        {/* ── DROPDOWN OPTIONS TAB ── */}
        {activeTab === "dropdownOptions" && (
          <div className="tab-content">
            <div className="list-header">
              {/* added margin top cuz other tab has button but this page doesnt have */}
              <h1 style={{ marginTop: "2px" }}>Dropdown Options</h1>
            </div>
            <div className="config-lists-grid">
              <ConfigurableListEditor
                title="Status (Dispatch Log)"
                list_type="STATUS" module="DISPATCH"
              />
              <ConfigurableListEditor
                title="Status (Monitoring Records)"
                list_type="STATUS" module="MONITORING"
              />
              <ConfigurableListEditor
                title="Type"
                description="Shared across all tabs. Locked to 'Installation' on Internet Install &amp; Cignal Play. Hidden on Client Concerns."
                list_type="TYPE" module="DISPATCH"
              />
              <ConfigurableListEditor
                title="Chat Type"
                description="Shared across all tabs. 'For Installation' is hidden on Client Concerns."
                list_type="CHAT_TYPE" module="DISPATCH"
              />
            </div>
          </div>
        )}
        {/* CSR Modals */}
        <AccountFormModal
          isOpen={showCSRForm}
          editCSR={editCSR}
          onClose={() => setShowCSRForm(false)}
          onSubmit={handleCSRSubmit}
          name={csrName}
          setName={setCsrName}
          email={csrEmail}
          setEmail={setCsrEmail}
          password={csrPassword}
          setPassword={setCsrPassword}
          retypePassword={csrRetypePassword}
          setRetypePassword={setCsrRetypePassword}
          currentPassword={csrCurrentPassword}
          setCurrentPassword={setCsrCurrentPassword}
          saving={csrSaving}
          onUpdatePassword={handleUpdatePassword}
          updatePasswordLoading={passwordSaving}
          requireCurrentPw={!!editCSR && user?.id === editCSR.id}
        />
        <DeleteConfirmModal
          isOpen={!!deleteCSRTarget}
          targetName={deleteCSRTarget?.name ?? ""}
          targetLabel="CSR"
          confirmName={deleteConfirmName}
          setConfirmName={setDeleteConfirmName}
          onClose={() => setDeleteCSRTarget(null)}
          onSubmit={handleConfirmDeleteCSR}
          saving={deleteSaving}
          danger
        />

        {/* Technician Modals */}
        <TechnicianFormModal
          isOpen={showTechForm}
          editTech={editTech}
          onClose={() => setShowTechForm(false)}
          onSubmit={handleTechSubmit}
          name={techName}
          setName={setTechName}
          contactNumber={techContactNumber}
          setContactNumber={setTechContactNumber}
          targetDay={techTargetDay}
          setTargetDay={setTechTargetDay}
          targetMonth={techTargetMonth}
          setTargetMonth={setTechTargetMonth}
          saving={techSaving}
        />
        <DeleteConfirmModal
          isOpen={!!deleteTechTarget}
          targetName={deleteTechTarget?.name ?? ""}
          targetLabel="Technician"
          confirmName={deleteTechConfirmName}
          setConfirmName={setDeleteTechConfirmName}
          onClose={() => setDeleteTechTarget(null)}
          onSubmit={handleConfirmDeleteTech}
          saving={deleteTechSaving}
          danger
        />

        {/* Team Modal */}
        <TeamFormModal
          isOpen={showTeamForm}
          editTeam={editTeam}
          onClose={() => {
            setShowTeamForm(false);
            setSelectedTeamMembers([]);
          }}
          onSubmit={handleTeamSubmit}
          name={teamName}
          setName={setTeamName}
          saving={teamSaving}
          unassignedTechnicians={
            editTeam ? [] : technicians.filter((t) => t.team_id == null)
          }
          selectedMemberIds={selectedTeamMembers}
          onSelectedMembersChange={setSelectedTeamMembers}
        />
        <DeleteConfirmModal
          isOpen={!!deleteTeamTarget}
          targetLabel="Team"
          message={`Delete team "${deleteTeamTarget?.name}"? Members will be unassigned (not deleted).`}
          onClose={() => setDeleteTeamTarget(null)}
          onSubmit={handleConfirmDeleteTeam}
          saving={deleteTeamSaving}
        />

        {/* Target Modal */}
        <TargetFormModal
          isOpen={showTargetForm}
          editTarget={editTarget}
          onClose={() => setShowTargetForm(false)}
          onSubmit={handleTargetSubmit}
          month={targetMonth}
          setMonth={setTargetMonth}
          year={targetYear}
          setYear={setTargetYear}
          value={targetValue}
          setValue={setTargetValue}
          saving={targetSaving}
        />
        <DeleteConfirmModal
          isOpen={!!deleteTargetModal}
          targetLabel="Target"
          message={`Delete the target for ${deleteTargetModal?.month_label} ${deleteTargetModal?.year}?`}
          onClose={() => setDeleteTargetModal(null)}
          onSubmit={handleConfirmDeleteTarget}
          saving={deleteTargetSaving}
        />
        <PdfViewer
          open={manualOpen}
          file="/DIspatch-System-User-Manual.pdf"
          onClose={() => setManualOpen(false)}
        />
    </div>
  );
}