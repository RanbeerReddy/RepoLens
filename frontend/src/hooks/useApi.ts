import { useState, useEffect, useCallback } from 'react';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface UseApiResult<T> extends UseApiState<T> {
  refetch: () => Promise<void>;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
): UseApiResult<T> {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  const fetchData = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await fetcher();
      setState({ data, loading: false, error: null });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'An unexpected error occurred';
      setState({ data: null, loading: false, error: message });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { ...state, refetch: fetchData };
}

export function useLazyApi<TArgs extends unknown[], TResult>(
  fetcher: (...args: TArgs) => Promise<TResult>
) {
  const [state, setState] = useState<UseApiState<TResult>>({
    data: null,
    loading: false,
    error: null,
  });

  const execute = useCallback(
    async (...args: TArgs) => {
      setState({ data: null, loading: true, error: null });
      try {
        const data = await fetcher(...args);
        setState({ data, loading: false, error: null });
        return data;
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : 'An unexpected error occurred';
        setState({ data: null, loading: false, error: message });
        throw err;
      }
    },
    [fetcher]
  );

  return { ...state, execute };
}
