import api from "../lib/api";
import { useApiQuery } from "./useApiQuery";
import type { CSR } from "../lib/types";

export interface CreateAccountBody {
  name: string;
  email: string;
  password: string;
  current_password: string;
}

export interface UpdateAccountBody {
  name?: string;
  email?: string;
}

export function useAccounts() {
  const { data, loading, error, refetch } = useApiQuery<CSR[]>(
    "/auth/accounts",
    [],
    [],
    "accounts",
  );

  const createAccount = async (body: CreateAccountBody) => {
    const res = await api.post("/auth/accounts", body);
    refetch();
    return res.data.data as CSR;
  };

  const updateAccount = async (id: number, body: UpdateAccountBody) => {
    const res = await api.put(`/auth/accounts/${id}`, body);
    refetch();
    return res.data.data as CSR;
  };

  const updatePassword = async (id: number, newPassword: string, currentPassword?: string) => {
    const body: Record<string, string> = { new_password: newPassword };
    if (currentPassword) body.current_password = currentPassword;
    const res = await api.put(`/auth/accounts/${id}/password`, body);
    return res.data.data as CSR;
  };

  return { data, loading, error, refetch, createAccount, updateAccount, updatePassword };
}
