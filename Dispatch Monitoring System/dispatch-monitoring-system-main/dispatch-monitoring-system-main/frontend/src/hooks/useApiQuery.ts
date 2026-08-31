import { useState, useEffect, useCallback, useRef } from "react";
import api from "../lib/api";
import { useQuerySubscription } from "../lib/querySync";

interface UseApiQueryResult<T> {
  data: T;
  loading: boolean;
  isFetching: boolean;
  error: string | null;
  warnings: string[];
  refetch: () => Promise<void>;
}

export function useApiQuery<T>(
  url: string,
  deps: unknown[],
  initialValue: T,
  errorLabel: string,
): UseApiQueryResult<T> {
  const [data, setData] = useState<T>(initialValue);
  const [loading, setLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const isInitialLoad = useRef(true);

  const fetch = useCallback(async () => {
    try {
      if (isInitialLoad.current) {
        setLoading(true);
      } else {
        setIsFetching(true);
      }
      setError(null);
      const res = await api.get(url);
      setData(res.data.data);
      setWarnings(Array.isArray(res.data.warnings) ? res.data.warnings : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to load ${errorLabel}`);
    } finally {
      setLoading(false);
      setIsFetching(false);
      isInitialLoad.current = false;
    }
  }, [url, ...deps]);

  useQuerySubscription(url, fetch);

  useEffect(() => { fetch(); }, [fetch]);

  return { data, loading, isFetching, error, warnings, refetch: fetch };
}