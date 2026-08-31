import { useEffect, useState } from "react";
import { LayoutDashboard } from "lucide-react";
import api from "../lib/api";
import {
  useDashboardStats,
  useStaffStats,
  useTeamStats,
  useAdminStats,
  useMonitoringSummary,
  useTargets,
  type DashboardFilters,
} from "../hooks/useDashboard";
import { useConfigOptions } from "../hooks/useConfigOptions";
import { useToast } from "../context/ToastContext";
import type { MonitoringStatusData } from "../hooks/useDashboard";
import DateRangePicker from "../components/filters/DateRangePicker";
import DashboardSkeleton from "../components/DashboardSkeleton";
import {
  BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  XAxis, YAxis, CartesianGrid, Legend,
  ReferenceLine,
} from "recharts";
import {
  Package, Wrench, AlertCircle, Equal, Download, RefreshCw,
  CheckCircle2, Clock, Activity, Ban,
} from "lucide-react";
import "../styles/Dashboard.css";

function closeRateClass(rate: number): string {
  if (rate >= 70) return "pill pill-green";
  if (rate >= 40) return "pill pill-yellow";
  return "pill pill-red";
}

function rankBadge(rank: number): string {
  if (rank === 1) return "rank-badge rank-gold";
  if (rank === 2) return "rank-badge rank-silver";
  if (rank === 3) return "rank-badge rank-bronze";
  return "rank-badge";
}

function WarningBanner({ warnings }: { warnings: string[] }) {
  if (!warnings || warnings.length === 0) return null;

  return (
    <div className="dashboard-warning-banner">
      <div className="dashboard-warning-text">
        {warnings.length === 1 ? (
          <span>{warnings[0]}</span>
        ) : (
          <ul className="dashboard-warning-list">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function MonitoringStatusPie({
  monitoringStatus,
  pieMode,
  onPieModeChange,
  filtered,
  periodLabel,
}: {
  monitoringStatus: MonitoringStatusData;
  pieMode: "all" | "internet_install" | "cignal_play" | "client_concerns";
  onPieModeChange: (mode: "all" | "internet_install" | "cignal_play" | "client_concerns") => void;
  filtered: boolean;
  periodLabel: string;
}) {
  const { options: statusOptions } = useConfigOptions("STATUS", "MONITORING");

  const statusCounts =
    pieMode === "internet_install" ? monitoringStatus.internet_install :
    pieMode === "cignal_play" ? monitoringStatus.cignal_play :
    pieMode === "client_concerns" ? monitoringStatus.client_concerns :
    monitoringStatus.overall;

  const statusPieData = statusOptions.map((opt) => ({
    name: opt.label,
    value: statusCounts[opt.label] ?? 0,
    color: opt.color,
  }));

  const hasData = statusPieData.some((d) => d.value > 0);
  const emptyStroke = hasData ? {} : { stroke: "#000", strokeWidth: 0.2 };
  const isLegendWide = statusPieData.length >= 5;
  const legendHalf = Math.ceil(statusPieData.length / 2);
  const leftLegends = statusPieData.slice(0, legendHalf);
  const rightLegends = statusPieData.slice(legendHalf);

  const togglePieMode = () => onPieModeChange(
    pieMode === "all" ? "internet_install" :
    pieMode === "internet_install" ? "cignal_play" :
    pieMode === "cignal_play" ? "client_concerns" : "all"
  );

  const modeLabel = pieMode === "all" ? "All Records" :
    pieMode === "internet_install" ? "Internet Install" :
    pieMode === "cignal_play" ? "Cignal Play" : "Client Concerns";

  return (
    <div className="status-donut-card status-donut-card--wide">
      <div className="donut-and-stats">
        <div className="donut-chart-area" onClick={togglePieMode} style={{ cursor: "pointer" }}>
          <div className="donut-chart-wrapper">
            <ResponsiveContainer width={260} height={260}>
              <PieChart>
                <Pie
                  data={hasData ? statusPieData : [{ name: "", value: 1, color: "transparent" }]}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={80}
                  outerRadius={110}
                  paddingAngle={2}
                  animationDuration={800}
                  {...emptyStroke}
                >
                  {hasData
                    ? statusPieData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))
                    : <Cell fill="transparent" />}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="donut-center-label">
              <span>{modeLabel}</span>
            </div>
          </div>
          <p className="donut-caption">
            {modeLabel} monitoring status{filtered ? ` for ${periodLabel}` : ""} — click to toggle
          </p>
        </div>

        <div className={isLegendWide ? "status-legend status-legend--2col" : "status-legend"}>
          {isLegendWide ? (
            <>
              <div className="status-legend-col">
                {leftLegends.map((d, i) => (
                  <div key={d.name}>
                    <div className="status-legend-item">
                      <span className="legend-dot" style={{ background: d.color }} />
                      <span className="status-legend-label">{d.name}</span>
                      <span className="status-legend-value" style={{ color: d.color }}>{d.value}</span>
                    </div>
                    {i < leftLegends.length - 1 && <div className="status-legend-divider" />}
                  </div>
                ))}
              </div>
              <div className="status-legend-col">
                {rightLegends.map((d, i) => (
                  <div key={d.name}>
                    <div className="status-legend-item">
                      <span className="legend-dot" style={{ background: d.color }} />
                      <span className="status-legend-label">{d.name}</span>
                      <span className="status-legend-value" style={{ color: d.color }}>{d.value}</span>
                    </div>
                    {i < rightLegends.length - 1 && <div className="status-legend-divider" />}
                  </div>
                ))}
              </div>
            </>
          ) : (
            statusPieData.map((d, i) => (
              <div key={d.name}>
                <div className="status-legend-item">
                  <span className="legend-dot" style={{ background: d.color }} />
                  <span className="status-legend-label">{d.name}</span>
                  <span className="status-legend-value" style={{ color: d.color }}>{d.value}</span>
                </div>
                {i < statusPieData.length - 1 && <div className="status-legend-divider" />}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

const monitoringTabLabels: Record<string, string> = {
  INTERNET_INSTALL: "Internet Install",
  CIGNAL_PLAY: "Cignal Play",
  CLIENT_CONCERNS: "Client Concerns",
};

function MonitoringSummarySection({
  data,
  loading,
  periodLabel,
}: {
  data: Record<string, { total: number; completed: number; cancelled: number }> | null;
  loading: boolean;
  periodLabel: string;
}) {
  return (
    <div className="dashboard-section">
      <div className="section-head">
        <h2>Monitoring Summary</h2>
      </div>
      <p className="period-meta">Monitoring activity for {periodLabel}</p>
      {loading && <div className="dashboard-loading">Loading monitoring summary...</div>}
      {data && (
        <div className="monitoring-summary-grid">
          {Object.entries(data).map(([tabType, info]) => (
            <div key={tabType} className="monitoring-summary-card">
              <h3>{monitoringTabLabels[tabType] ?? tabType}</h3>
              <div className="monitoring-summary-stats">
                <div className="monitoring-stat">
                  <span className="monitoring-stat-value">{info.total}</span>
                  <span className="monitoring-stat-label">Total</span>
                </div>
                <div className="monitoring-stat monitoring-stat--done">
                  <span className="monitoring-stat-value">{info.completed}</span>
                  <span className="monitoring-stat-label">Completed</span>
                </div>
                <div className="monitoring-stat monitoring-stat--cancelled">
                  <span className="monitoring-stat-value">{info.cancelled}</span>
                  <span className="monitoring-stat-label">Cancelled</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [filters, setFilters] = useState<DashboardFilters>({});
  const [techStatsView, setTechStatsView] = useState<"staff" | "team">("staff");
  const [pieMode, setPieMode] = useState<"all" | "internet_install" | "cignal_play" | "client_concerns">("all");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [now, setNow] = useState(Date.now());

  const stats = useDashboardStats(filters);
  const staff = useStaffStats(filters);
  const teamStats = useTeamStats(filters);
  const admins = useAdminStats(filters);
  const targets = useTargets(filters);
  const monitoringSummary = useMonitoringSummary(filters);

  const periodLabel = stats.data?.period.label ?? "All Records";
  const filtered = periodLabel !== "All Records";

  const { addToast } = useToast();

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (stats.error) addToast("Failed to load Operational Overview.", "error");
  }, [stats.error]);

  useEffect(() => {
    if (staff.error) addToast("Failed to load Technician Statistics.", "error");
  }, [staff.error]);

  useEffect(() => {
    if (teamStats.error) addToast("Failed to load Technician Statistics.", "error");
  }, [teamStats.error]);

  useEffect(() => {
    if (admins.error) addToast("Failed to load Admin Statistics.", "error");
  }, [admins.error]);

  useEffect(() => {
    if (targets.error) addToast("Failed to load Monthly Install Targets.", "error");
  }, [targets.error]);

  useEffect(() => {
    if (monitoringSummary.error) addToast("Failed to load Monitoring Summary.", "error");
  }, [monitoringSummary.error]);

  const avgTarget =
    targets.data.length > 0
      ? Math.round(targets.data.reduce((sum, t) => sum + t.target, 0) / targets.data.length)
      : null;

  const targetLineData = targets.data.map((t) => ({
    name: `${t.month_label.slice(0, 3)} ${t.year}`,
    Target: t.target,
    Actual: t.actual,
    Remaining: t.remaining,
    pct: t.percentage,
  }));

  const handleExportExcel = async () => {
    if (isExporting) return;

    setIsExporting(true);
    try {
      const params = new URLSearchParams();
      if (filters.date_from) params.set("date_from", filters.date_from);
      if (filters.date_to) params.set("date_to", filters.date_to);
      if (pieMode !== "all") params.set("pie_mode", pieMode);
      const qs = params.toString();

      const res = await api.get(`/dashboard/export/excel${qs ? `?${qs}` : ""}`, {
        responseType: "blob",
      });

      const blob = new Blob([res.data], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const label = periodLabel.replace(/[^a-zA-Z0-9]/g, "_").toLowerCase();
      a.download = `dashboard_${label}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      addToast("Failed to export Excel.", "error");
    } finally {
      setIsExporting(false);
    }
  };

  const handleRefresh = async () => {
    if (isRefreshing) return;

    setIsRefreshing(true);
    setNow(Date.now());
    try {
      await Promise.all([
        stats.refetch(),
        staff.refetch(),
        teamStats.refetch(),
        admins.refetch(),
        targets.refetch(),
        monitoringSummary.refetch(),
      ]);
    } catch {
      addToast("Failed to refresh dashboard data.", "error");
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <div className="dashboard-title-row">
          <div>
            <h1><LayoutDashboard size={24} /> Dashboard</h1>
            <p className="dashboard-timestamp">
              {new Date(now).toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
                hour: "numeric",
                minute: "2-digit",
                second: "2-digit",
              })}
            </p>
          </div>
          <div className="dashboard-actions">
            <DateRangePicker
              dateFrom={filters.date_from}
              dateTo={filters.date_to}
              onChange={({ date_from, date_to }) => setFilters({ date_from, date_to })}
            />
            <button className="dashboard-export-btn" onClick={handleExportExcel} disabled={isExporting}>
              <Download size={18} />
              <span>{isExporting ? "Exporting..." : "Export"}</span>
            </button>
            <button className="dashboard-refresh-btn" onClick={handleRefresh} disabled={isRefreshing}>
              <RefreshCw className={`dashboard-refresh-icon ${isRefreshing ? "is-spinning" : ""}`} size={18} />
            </button>
          </div>
        </div>
      </div>

        <div className="dashboard-content">

        {stats.loading && <DashboardSkeleton />}

        {stats.data && (
          <>
            {/* Operational KPIs */}
            <div className="dashboard-section">
              <h2>Operational Overview</h2>
              <div className="kpi-grid kpi-grid--4">
                <div className="kpi-card kpi-card--accent-amber">
                  <Clock className="kpi-icon" size={20} />
                  <div className="kpi-content">
                    <span className="kpi-number">{stats.data.pending_monitoring.total}</span>
                    <span className="kpi-label">For Dispatch</span>
                    <span className="kpi-breakdown">{stats.data.install_stats.for_dispatch} Install &middot; {stats.data.repair_stats.for_dispatch} Repair</span>
                  </div>
                </div>
                <div className="kpi-card kpi-card--accent-blue">
                  <Activity className="kpi-icon" size={20} />
                  <div className="kpi-content">
                    <span className="kpi-number">{stats.data.stats.ongoing}</span>
                    <span className="kpi-label">Ongoing</span>
                    <span className="kpi-breakdown">{stats.data.install_stats.ongoing} Install &middot; {stats.data.repair_stats.ongoing} Repair</span>
                  </div>
                </div>
                <div className="kpi-card kpi-card--accent-green">
                  <CheckCircle2 className="kpi-icon" size={20} />
                  <div className="kpi-content">
                    <span className="kpi-number">{stats.data.stats.closed}</span>
                    <span className="kpi-label">{filtered ? "Closed (this period)" : "Total Closed"}</span>
                  </div>
                </div>
                <div className="kpi-card kpi-card--accent-red">
                  <Ban className="kpi-icon" size={20} />
                  <div className="kpi-content">
                    <span className="kpi-number">{stats.data.stats.cancelled}</span>
                    <span className="kpi-label">{filtered ? "Cancelled (this period)" : "Total Cancelled"}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Overview */}
            <div className="dashboard-section">
              <h2>Overview</h2>
              <p className="period-meta">Dispatch records for {periodLabel}</p>
              <WarningBanner warnings={stats.warnings} />
              <div className="overview-outer">
                <div className="overview-layout">
                  <div className="kpi-stack">
                    <div className="kpi-card">
                      <Equal className="kpi-icon" size={20} />
                      <span className="kpi-number">{stats.data.stats.total_dispatches}</span>
                      <span className="kpi-label">{filtered ? "New Dispatches" : "Total Dispatches"}</span>
                    </div>
                    <div className="kpi-card">
                      <Package className="kpi-icon" size={20} />
                      <span className="kpi-number">{stats.data.stats.installs}</span>
                      <span className="kpi-label">{filtered ? "New Installations" : "Installations"}</span>
                    </div>
                    <div className="kpi-card">
                      <Wrench className="kpi-icon" size={20} />
                      <span className="kpi-number">{stats.data.stats.repairs}</span>
                      <span className="kpi-label">{filtered ? "New Repairs" : "Repairs"}</span>
                    </div>
                    <div className="kpi-card">
                      <AlertCircle className="kpi-icon" size={20} />
                      <span className="kpi-number">{stats.data.stats.concerns}</span>
                      <span className="kpi-label">{filtered ? "New Concerns" : "Concerns"}</span>
                    </div>
                  </div>
                  <MonitoringStatusPie monitoringStatus={stats.data.monitoring_status} pieMode={pieMode} onPieModeChange={setPieMode} filtered={filtered} periodLabel={periodLabel} />
                </div>
              </div>
            </div>

          </>
        )}

        {/* Monitoring Summary */}
        <MonitoringSummarySection
          data={monitoringSummary.data}
          loading={monitoringSummary.loading}
          periodLabel={periodLabel}
        />

        {/* Monthly targets */}
        <div className="dashboard-section">
          <h2>Monthly Install Targets</h2>
          {targets.loading && <div className="dashboard-loading">Loading targets...</div>}
          <WarningBanner warnings={targets.warnings} />

          {!targets.loading && targets.data.length > 0 && (
            <div className="chart-card">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={targetLineData} margin={{ top: 10, right: 24, left: 0, bottom: 0 }} barCategoryGap="20%" barGap={4}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border, #e2e8f0)" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (!active || !payload?.length) return null;
                      const rawPoint = targetLineData.find((d) => d.name === label);
                      return (
                        <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "8px 12px", fontSize: 13 }}>
                          <p style={{ margin: "0 0 4px", fontWeight: 600 }}>{label}</p>
                          {payload.map((entry) => (
                            <div key={String(entry.dataKey)} style={{ color: entry.color, margin: "2px 0" }}>
                              {entry.name}: {entry.value}
                            </div>
                          ))}
                          {rawPoint && (
                            <div style={{ color: "#f59e0b", margin: "2px 0" }}>
                              Remaining: {rawPoint.Remaining}
                            </div>
                          )}
                        </div>
                      );
                    }}
                  />
                  <Legend />
                  {avgTarget !== null && (
                    <ReferenceLine
                      y={avgTarget}
                      stroke="#94a3b8"
                      strokeDasharray="4 4"
                      label={{ value: `Avg target: ${avgTarget}`, position: "insideTopRight", fontSize: 11, fill: "#94a3b8" }}
                    />
                  )}
                  <Bar dataKey="Target" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Actual" fill="#3533cd" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>

              <div className="target-minicards">
                {targets.data.map((t) => {
                  const isDone = t.percentage >= 100;
                  return (
                    <div
                      key={`${t.year}-${t.month}`}
                      className={`target-minicard${isDone ? " target-minicard--done" : ""}`}
                    >
                      <span className="target-minicard-month">{t.month_label.slice(0, 3).toUpperCase()}</span>
                      <span className="target-minicard-pct">{t.percentage}%</span>
                      <span className="target-minicard-detail">
                        {t.actual}/{t.target} · {isDone ? "done" : `${t.remaining} left`}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {!targets.loading && targets.data.length === 0 && (
            <p>No targets configured for this period. Set them under Management → Target Installment.</p>
          )}
        </div>

        {/* Technicals */}
        <div className="dashboard-section">
          <div className="section-head">
            <h2>Technicals — {techStatsView === "staff" ? "By Staff" : "By Team"}</h2>
            <div className="toggle-group">
              <button
                className={`toggle-btn ${techStatsView === "staff" ? "active" : ""}`}
                onClick={() => setTechStatsView("staff")}
              >
                By Staff
              </button>
              <button
                className={`toggle-btn ${techStatsView === "team" ? "active" : ""}`}
                onClick={() => setTechStatsView("team")}
              >
                By Team
              </button>
            </div>
          </div>
          <p className="period-meta">Dispatch activity for {periodLabel}</p>
          <WarningBanner warnings={techStatsView === "staff" ? staff.warnings : teamStats.warnings} />

          {techStatsView === "staff" && (
            <>
              {staff.loading && <div className="dashboard-loading">Loading staff stats...</div>}
              {!staff.loading && (
                <div className="table-scroll">
                  <table className="admin-stats-table">
                    <thead>
                      <tr>
                        <th>Rank</th>
                        <th>Technician</th>
                        <th>Installs</th>
                        <th>Repairs</th>
                        <th>Total</th>
                        <th>Target/Day</th>
                        <th>Target/Month</th>
                        <th>% of Product</th>
                        <th>Per Day (avg)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {staff.data.map((s) => (
                        <tr key={s.technician}>
                          <td>
                            <span className={rankBadge(s.productivity_rank)}>
                              {s.productivity_rank}
                            </span>
                          </td>
                          <td>{s.technician}</td>
                          <td>{s.installs}</td>
                          <td>{s.repairs}</td>
                          <td><strong>{s.total}</strong></td>
                          <td>{s.target_per_day}</td>
                          <td>{s.target_per_month}</td>
                          <td>
                            {s.percentage_of_product !== null ? (
                              <span className={closeRateClass(s.percentage_of_product)}>
                                {s.percentage_of_product}%
                              </span>
                            ) : "—"}
                          </td>
                          <td>{s.per_day}</td>
                        </tr>
                      ))}
                      {staff.data.length === 0 && (
                        <tr><td colSpan={9}>No technician data for this period</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {techStatsView === "team" && (
            <>
              {teamStats.loading && <div className="dashboard-loading">Loading team stats...</div>}
              {!teamStats.loading && (
                <div className="table-scroll">
                  <table className="admin-stats-table">
                    <thead>
                      <tr>
                        <th>Team</th>
                        <th>Members</th>
                        <th>Installs</th>
                        <th>Repairs</th>
                        <th>Total</th>
                        <th>Target/Day</th>
                        <th>Target/Month</th>
                        <th>% of Product</th>
                        <th>Per Day (avg)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {teamStats.data.map((t) => (
                        <tr key={t.team_id ?? "unassigned"}>
                          <td>{t.team}</td>
                          <td>{t.member_count}</td>
                          <td>{t.installs}</td>
                          <td>{t.repairs}</td>
                          <td><strong>{t.total}</strong></td>
                          <td>{t.target_per_day}</td>
                          <td>{t.target_per_month}</td>
                          <td>
                            {t.percentage_of_product !== null ? (
                              <span className={closeRateClass(t.percentage_of_product)}>
                                {t.percentage_of_product}%
                              </span>
                            ) : "—"}
                          </td>
                          <td>{t.per_day}</td>
                        </tr>
                      ))}
                      {teamStats.data.length === 0 && (
                        <tr><td colSpan={9}>No team data for this period</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>

        {/* Admin stats */}
        <div className="dashboard-section">
          <h2>Admin Stats</h2>
          <p className="period-meta">CSR activity for {periodLabel}</p>
          <WarningBanner warnings={admins.warnings} />
          {admins.loading && <div className="dashboard-loading">Loading admin stats...</div>}
          {!admins.loading && (
            <div className="table-scroll">
              <table className="admin-stats-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>CSR</th>
                    <th>Assigned</th>
                    <th>Dispatch Handled</th>
                    <th>Dispatch Closed</th>
                    <th>Close Rate</th>
                    <th>Concerns Handled</th>
                    <th>Concerns Closed</th>
                    <th>Concern Close Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {admins.data.map((a) => (
                    <tr key={a.csr}>
                      <td>
                        <span className={rankBadge(a.rank)}>
                          {a.rank}
                        </span>
                      </td>
                      <td>{a.csr}</td>
                      <td>{a.total_records}</td>
                      <td>{a.dispatch_handled}</td>
                      <td>{a.dispatch_closed}</td>
                      <td>
                        <span className={closeRateClass(a.dispatch_close_rate)}>
                          {a.dispatch_close_rate}%
                        </span>
                      </td>
                      <td>{a.concerns_handled}</td>
                      <td>{a.concerns_closed}</td>
                      <td>
                        <span className={closeRateClass(a.concerns_close_rate)}>
                          {a.concerns_close_rate}%
                        </span>
                      </td>
                    </tr>
                  ))}
                  {admins.data.length === 0 && (
                    <tr><td colSpan={9}>No admin data for this period</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}