import api from "../lib/api";
import { useApiQuery } from "./useApiQuery";
import type { Team } from "../lib/types";
export type { Team } from "../lib/types";

export function useTeams() {
  const { data, loading, error, refetch } = useApiQuery<Team[]>(
    "/teams",
    [],
    [],
    "teams",
  );

  const createTeam = async (body: { name: string }) => {
    const res = await api.post("/teams", body);
    refetch();
    return res.data.data as Team;
  };

  const updateTeam = async (id: number, body: { name?: string }) => {
    const res = await api.put(`/teams/${id}`, body);
    refetch();
    return res.data.data as Team;
  };

  const deleteTeam = async (id: number) => {
    await api.delete(`/teams/${id}`);
    refetch();
  };

  return {
    data,
    loading,
    error,
    refetch,
    createTeam,
    updateTeam,
    deleteTeam,
  };
}