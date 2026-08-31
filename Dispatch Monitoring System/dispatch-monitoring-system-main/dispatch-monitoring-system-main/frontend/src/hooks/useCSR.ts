import api from "../lib/api";
import { useApiQuery } from "./useApiQuery";
import type { CSR } from "../lib/types";

export type { CSR } from "../lib/types";

export function useCSR() {
  const { data, loading, error, refetch } = useApiQuery<CSR[]>(
    "/csr",
    [],
    [],
    "CSRs",
  );

  const createCSR = async (body: { name: string }) => {
    const res = await api.post("/csr", body);
    refetch();
    return res.data.data as CSR;
  };

  const updateCSR = async (id: number, body: { name: string }) => {
    const res = await api.put(`/csr/${id}`, body);
    refetch();
    return res.data.data as CSR;
  };

  const deleteCSR = async (id: number, confirmName: string) => {
    await api.delete(`/csr/${id}`, { data: { confirm_name: confirmName } });
    refetch();
  };

  return {
    data,
    loading,
    error,
    refetch,
    createCSR,
    updateCSR,
    deleteCSR,
  };
}
