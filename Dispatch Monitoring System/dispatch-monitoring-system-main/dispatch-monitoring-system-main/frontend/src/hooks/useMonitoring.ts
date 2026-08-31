import { useState, useEffect, useCallback, useRef } from "react";
import api from "../lib/api";
import { appendFilterParams } from "../lib/filterParams";
import { useQuerySubscription } from "../lib/querySync";
import type { MonitoringRecord, Dispatch, Pagination } from "../lib/types";

export type { MonitoringRecord, Dispatch } from "../lib/types";

export interface MonitoringFilters {
  tab_type?: string;
  status_id?: number;
  type_id?: number;
  csr?: number;
  client?: string;
  sales_agent?: string;
  ticket_number?: string;
  job_order?: string;
  done?: boolean;
  ongoing?: boolean;
  date_from?: string;
  date_to?: string;
  page?: number;
  limit?: number;
}

export interface MarkDoneResult {
  record: MonitoringRecord;
  dispatch: Dispatch;
}

export interface CancelResult {
  record: MonitoringRecord;
  dispatch: Dispatch;
}

export function useMonitoring(filters: MonitoringFilters = {}) {
  const [data, setData] = useState<MonitoringRecord[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isInitialLoad = useRef(true);

  const fetch = useCallback(async () => {
    try {
      if (isInitialLoad.current) {
        setLoading(true);
      }
      setError(null);
      const params = new URLSearchParams();
      appendFilterParams(params, filters);
      const res = await api.get(`/monitoring?${params}`);
      setData(res.data.data);
      setPagination(res.data.pagination);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load records");
    } finally {
      setLoading(false);
      isInitialLoad.current = false;
    }
  }, [filters]);

  useQuerySubscription("monitoring", fetch);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const createRecord = async (body: Record<string, unknown>) => {
    const res = await api.post("/monitoring", body);
    fetch();
    return res.data.data as MonitoringRecord;
  };

  const updateRecord = async (
    id: number,
    body: Record<string, unknown> & { teams?: number[] }
  ) => {
    const res = await api.put(`/monitoring/${id}`, body);
    fetch();
    return res.data.data as MonitoringRecord;
  };

  const markAsDone = async (
    id: number,
    extra: Record<string, unknown> = {}
  ): Promise<MarkDoneResult> => {
    const res = await api.post(`/monitoring/${id}/done`, {
      ...extra,
    });
    fetch();
    return res.data.data as MarkDoneResult;
  };

  const cancelRecord = async (id: number, reason: string): Promise<CancelResult> => {
    const res = await api.post(`/monitoring/${id}/cancel`, { reason });
    fetch();
    return res.data.data as CancelResult;
  };

  const deleteRecord = async (id: number, confirmName: string) => {
    await api.delete(`/monitoring/${id}`, { data: { confirm_name: confirmName } });
    fetch();
  };

  return {
    data,
    pagination,
    loading,
    error,
    refetch: fetch,
    createRecord,
    updateRecord,
    markAsDone,
    cancelRecord,
    deleteRecord,
  };
}