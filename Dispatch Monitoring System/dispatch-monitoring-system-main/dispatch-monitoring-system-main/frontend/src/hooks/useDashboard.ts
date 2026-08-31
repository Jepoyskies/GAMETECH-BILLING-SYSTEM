import api from "../lib/api";
import { useApiQuery } from "./useApiQuery";
import { appendFilterParams } from "../lib/filterParams";

export interface DashboardFilters {
  date_from?: string;
  date_to?: string;
}

interface DashboardPeriod {
  label: string;
  date_from: string | null;
  date_to: string | null;
}

export interface MonitoringStatusData {
  overall: Record<string, number>;
  internet_install: Record<string, number>;
  cignal_play: Record<string, number>;
  client_concerns: Record<string, number>;
}

interface DashboardStats {
  as_of: string;
  period: DashboardPeriod;
  stats: {
    total_dispatches: number;
    installs: number;
    repairs: number;
    concerns: number;
    ongoing: number;
    closed: number;
    cancelled: number;
  };
  pending_monitoring: {
    total: number;
    internet_install: number;
    cignal_play: number;
    client_concerns: number;
  };
  install_stats: {
    for_dispatch: number;
    ongoing: number;
  };
  repair_stats: {
    for_dispatch: number;
    ongoing: number;
  };
  monitoring_status: MonitoringStatusData;
}

interface StaffStat {
  technician_id: number;
  technician: string;
  installs: number;
  repairs: number;
  total: number;
  target_per_day: number;
  target_per_month: number;
  percentage_of_product: number | null;
  per_day: number;
  productivity_rank: number;
}

export interface TeamStat {
  team_id: number | null;
  team: string;
  member_count: number;
  installs: number;
  repairs: number;
  total: number;
  target_per_day: number;
  target_per_month: number;
  percentage_of_product: number | null;
  per_day: number;
}

interface AdminStat {
  csr_id: number;
  csr: string;
  total_records: number;
  dispatch_handled: number;
  dispatch_closed: number;
  dispatch_cancelled: number;
  dispatch_close_rate: number;
  concerns_handled: number;
  concerns_closed: number;
  concerns_cancelled: number;
  concerns_close_rate: number;
  rank: number;
}

export interface MonthlyTarget {
  id: number;
  month: number;
  month_label: string;
  year: number;
  target: number;
  actual: number;
  remaining: number;
  percentage: number;
}

export interface MonitoringSummaryItem {
  total: number;
  completed: number;
  cancelled: number;
}

export type MonitoringSummary = Record<string, MonitoringSummaryItem>;

function buildDashboardParams(filters: DashboardFilters): string {
  const params = new URLSearchParams();
  appendFilterParams(params, {
    date_from: filters.date_from,
    date_to: filters.date_to,
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useDashboardStats(filters: DashboardFilters) {
  return useApiQuery<DashboardStats | null>(
    `/dashboard/stats${buildDashboardParams(filters)}`,
    [filters.date_from, filters.date_to],
    null,
    "stats",
      );
}

export function useStaffStats
(filters: DashboardFilters) {
  return useApiQuery<StaffStat[]>(
    `/dashboard/by-staff${buildDashboardParams(filters)}`,
    [filters.date_from, filters.date_to],
    [],
    "staff stats",
  );
}

export function useTeamStats(filters: DashboardFilters) {
  return useApiQuery<TeamStat[]>(
    `/dashboard/by-team${buildDashboardParams(filters)}`,
    [filters.date_from, filters.date_to],
    [],
    "team stats",
  );
}

export function useAdminStats(filters: DashboardFilters) {
  return useApiQuery<AdminStat[]>(
    `/dashboard/by-admin${buildDashboardParams(filters)}`,
    [filters.date_from, filters.date_to],
    [],
    "admin stats",
  );
}

export function useMonitoringSummary(filters: DashboardFilters) {
  return useApiQuery<MonitoringSummary | null>(
    `/dashboard/monitoring-summary${buildDashboardParams(filters)}`,
    [filters.date_from, filters.date_to],
    null,
    "monitoring summary",
  );
}

export function useTargets(filters: DashboardFilters) {
  const { data, loading, error, warnings, refetch } = useApiQuery<MonthlyTarget[]>(
    `/dashboard/targets${buildDashboardParams(filters)}`,
    [filters.date_from, filters.date_to],
    [],
    "targets",
  );

  return { data, loading, error, warnings, refetch };
}

export function useManageTargets() {
  const { data, loading, error, refetch } = useApiQuery<MonthlyTarget[]>(
    "/dashboard/targets",
    [],
    [],
    "targets",
  );

  const upsertTarget = async (month: number, year: number, target: number) => {
    const res = await api.post("/dashboard/targets", { month, year, target });
    refetch();
    return res.data.data;
  };

  const deleteTarget = async (id: number) => {
    await api.delete(`/dashboard/targets/${id}`);
    refetch();
  };

  return { data, loading, error, refetch, upsertTarget, deleteTarget };
}