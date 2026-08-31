import api from "../lib/api";
import { useApiQuery } from "./useApiQuery";
import type { Technician } from "../lib/types";

export type { Technician } from "../lib/types";

export function useTechnicians() {
  const { data, loading, error, refetch } = useApiQuery<Technician[]>(
    "/technicians",
    [],
    [],
    "technicians",
  );

  const createTechnician = async (body: {
    name: string;
    contact_number?: string | null;
    target_per_day?: number;
    target_per_month?: number;
    team_id?: number | null;
  }) => {
    const res = await api.post("/technicians", body);
    refetch();
    return res.data.data as Technician;
  };

  const updateTechnician = async (
    id: number,
    body: {
      name?: string;
      contact_number?: string | null;
      target_per_day?: number;
      target_per_month?: number;
      team_id?: number | null;
    }
  ) => {
    const res = await api.put(`/technicians/${id}`, body);
    refetch();
    return res.data.data as Technician;
  };

  const deleteTechnician = async (id: number, confirmName: string) => {
    await api.delete(`/technicians/${id}`, { data: { confirm_name: confirmName } });
    refetch();
  };

  return {
    data,
    loading,
    error,
    refetch,
    createTechnician,
    updateTechnician,
    deleteTechnician,
  };
}