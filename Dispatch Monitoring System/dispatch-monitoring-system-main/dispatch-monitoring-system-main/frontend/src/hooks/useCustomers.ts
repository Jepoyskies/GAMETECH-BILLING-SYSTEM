import { useState, useEffect, useCallback, useRef } from "react";
import api from "../lib/api";
import type {
  Customer,
  CustomerStats,
  CustomerJob,
  Pagination,
} from "../lib/types";

export type CustomerSort = "name_asc" | "created_desc";

export interface CustomerFilters {
  search?: string;
  sort?: CustomerSort;
  page?: number;
  limit?: number;
}

export function useCustomers(filters: CustomerFilters = {}) {
  const [data, setData] = useState<Customer[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isInitialLoad = useRef(true);

  const { search, sort, page, limit } = filters;

  const fetchCustomers = useCallback(async () => {
    try {
      if (isInitialLoad.current) {
        setLoading(true);
      }
      setError(null);
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (sort) params.set("sort", sort);
      if (page) params.set("page", String(page));
      if (limit) params.set("limit", String(limit));
      const res = await api.get(`/customers?${params}`);
      setData(res.data.data);
      setPagination(res.data.pagination);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customers");
    } finally {
      setLoading(false);
      isInitialLoad.current = false;
    }
  }, [search, sort, page, limit]);

  useEffect(() => {
    fetchCustomers();
  }, [fetchCustomers]);

  const createCustomer = async (body: {
    name: string;
    address: string;
    contact_number: string;
    account_number?: string | null;
    email?: string | null;
    barangay_city?: string | null;
    latitude?: number | null;
    longitude?: number | null;
  }) => {
    const res = await api.post("/customers", body);
    fetchCustomers();
    return res.data.data as Customer;
  };

  return { data, pagination, loading, error, refetch: fetchCustomers, createCustomer };
}

export function useCustomerDetail(id: number, jobsPage: number, jobsLimit = 30) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [stats, setStats] = useState<CustomerStats | null>(null);
  const [jobs, setJobs] = useState<CustomerJob[]>([]);
  const [jobsPagination, setJobsPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCustomer = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [c, s] = await Promise.all([
        api.get(`/customers/${id}`),
        api.get(`/customers/${id}/stats`),
      ]);
      setCustomer(c.data.data);
      setStats(s.data.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customer");
    } finally {
      setLoading(false);
    }
  }, [id]);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await api.get(
        `/customers/${id}/jobs?page=${jobsPage}&limit=${jobsLimit}`
      );
      setJobs(res.data.data);
      setJobsPagination(res.data.pagination);
    } catch {
      setError((e) => e ?? "Failed to load job history");
    }
  }, [id, jobsPage, jobsLimit]);

  useEffect(() => {
    fetchCustomer();
  }, [fetchCustomer]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const updateCustomer = async (body: Partial<Customer>) => {
    const res = await api.put(`/customers/${id}`, body);
    await fetchCustomer();
    await fetchJobs();
    return res.data.data as Customer;
  };

  const deleteCustomer = async (confirmName: string) => {
    await api.delete(`/customers/${id}`, { data: { confirm_name: confirmName } });
  };

  return {
    customer,
    stats,
    jobs,
    jobsPagination,
    loading,
    error,
    refetch: fetchCustomer,
    updateCustomer,
    deleteCustomer,
  };
}
