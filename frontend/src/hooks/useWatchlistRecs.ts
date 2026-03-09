import { useState, useCallback } from 'react';
import { fetchWatchlistRecs } from '../api/endpoints';
import type { WatchlistRec } from '../api/types';

export function useWatchlistRecs() {
  const [results, setResults] = useState<WatchlistRec[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback((ids: number[]) => {
    setLoading(true);
    setError(null);
    fetchWatchlistRecs(ids)
      .then(r => setResults(r.recommendations))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return { results, loading, error, fetch };
}
