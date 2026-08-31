import { useState, useEffect, useCallback, useRef } from "react";
import api from "../lib/api";
import { appendFilterParams } from "../lib/filterParams";
import { useQuerySubscription } from "../lib/querySync";
import type { Dispatch, CursorPagination } from "../lib/types";

export type { Dispatch } from "../lib/types";

export interface DispatchFilters {
  status_id?: number;
  type_id?: number;
  source_tab?: string;
  chat_type_id?: number;
  csr?: number;
  client?: string;
  teams?: number[];
  date_from?: string;
  date_to?: string;
  done_from?: string;
  done_to?: string;
  time_start_from?: string;
  time_start_to?: string;
  sort_by?: "date" | "done_at";
  ticket_number?: string;
  job_details?: string;
  address?: string;
  cursor?: number;
  limit?: number;
}

export function useDispatches(filters: DispatchFilters = {}) {
  const [data, setData] = useState<Dispatch[]>([]);
  const [pagination, setPagination] = useState<CursorPagination | null>(null);
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
      const res = await api.get(`/dispatches?${params}`);
      setData(res.data.data);
      setPagination(res.data.pagination);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dispatches");
    } finally {
      setLoading(false);
      isInitialLoad.current = false;
    }
  }, [filters]);

  useQuerySubscription("dispatches", fetch);

  useEffect(() => { fetch(); }, [fetch]);

  const updateDispatch = async (
    id: number,
    body: Record<string, unknown> & { teams?: number[] }
  ) => {
    const res = await api.put(`/dispatches/${id}`, body);
    fetch();
    return res.data.data as Dispatch;
  };

  const deleteDispatch = async (id: number, confirmName: string) => {
    await api.delete(`/dispatches/${id}`, { data: { confirm_name: confirmName } });
    fetch();
  };

  return {
    data,
    pagination,
    loading,
    error,
    refetch: fetch,
    updateDispatch,
    deleteDispatch,
  };
}
