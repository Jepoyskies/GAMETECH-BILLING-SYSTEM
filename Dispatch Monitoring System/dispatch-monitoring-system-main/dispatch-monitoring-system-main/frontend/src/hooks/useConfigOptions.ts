import { useMemo } from "react";
import api from "../lib/api";
import { useQuerySubscription } from "../lib/querySync";
import { useApiQuery } from "./useApiQuery";
import type { ConfigListType, ConfigListModule, ConfigOption } from "../lib/types";
export type { ConfigListType, ConfigListModule, ConfigOption } from "../lib/types";

export function useConfigOptions(
  list_type: ConfigListType,
  module: ConfigListModule,
  showInactive = false
) {
  const endpoint = showInactive
    ? `/config-options?list_type=${list_type}&module=${module}&include_inactive=true`
    : `/config-options?list_type=${list_type}&module=${module}`;

  const { data, loading, error, refetch } = useApiQuery<ConfigOption[]>(
    endpoint,
    ["configOptions", list_type, module, showInactive ? "all" : "active"],
    [],
    "configOptions",
  );

  useQuerySubscription("configOptions", refetch);

  const options = useMemo(
    () => (data ?? []).sort((a, b) => a.sort_order - b.sort_order),
    [data]
  );

  const createOption = async (body: {
    label: string;
    color?: string;
    sort_order?: number;
  }) => {
    const res = await api.post("/config-options", {
      ...body,
      list_type,
      module,
    });
    refetch();
    return res.data.data as ConfigOption;
  };

  const updateOption = async (
    id: number,
    body: {
      label?: string;
      color?: string;
      sort_order?: number;
      active?: boolean;
    }
  ) => {
    const res = await api.put(`/config-options/${id}`, body);
    refetch();
    return res.data.data as ConfigOption;
  };

  const deactivateOption = async (id: number) => {
    await api.delete(`/config-options/${id}`);
    refetch();
  };

  const reorder = async (orderedIds: number[]) => {
    await api.post(`/config-options/reorder`, { list_type, module, ordered_ids: orderedIds });
    refetch();
  };

  return {
    options,
    loading,
    error,
    refetch,
    createOption,
    updateOption,
    deactivateOption,
    reorder,
  };
}

export function useDispatchOptions() {
  const status = useConfigOptions("STATUS", "DISPATCH", true);
  const type = useConfigOptions("TYPE", "DISPATCH", true);
  const chat_type = useConfigOptions("CHAT_TYPE", "DISPATCH", true);

  return {
    status: status.options,
    type: type.options,
    chat_type: chat_type.options,
    loading: status.loading || type.loading || chat_type.loading,
    error: status.error || type.error || chat_type.error,
    refetch: () => {
      status.refetch();
      type.refetch();
      chat_type.refetch();
    },
  };
}

