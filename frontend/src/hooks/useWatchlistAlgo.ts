import { useState, useCallback } from 'react';
import type { WatchlistAlgoResponse } from '../api/types';

export function useWatchlistAlgo(fetchFn: (ids: number[]) => Promise<WatchlistAlgoResponse>) {
  const [result, setResult] = useState<WatchlistAlgoResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback((ids: number[]) => {
    setLoading(true);
    setError(null);
    fetchFn(ids)
      .then(r => setResult(r))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [fetchFn]);

  return { result, loading, error, run };
}
