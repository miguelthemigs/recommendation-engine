import { useState, useCallback } from 'react';
import { fetchWatchlistCompare } from '../api/endpoints';
import { useBenchmarkContext } from '../context/BenchmarkContext';
import type { WatchlistCompareResponse } from '../api/types';

export function useWatchlistCompare() {
  const [result, setResult] = useState<WatchlistCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { setTimings } = useBenchmarkContext();

  const run = useCallback((ids: number[]) => {
    setLoading(true);
    setError(null);
    fetchWatchlistCompare(ids)
      .then(r => {
        setResult(r);
        setTimings({
          direct_ms:   r.direct.query_time_ms,
          bfs_ms:      r.bfs.query_time_ms,
          pagerank_ms: r.pagerank.query_time_ms,
          recorded_at: new Date().toISOString(),
        });
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [setTimings]);

  return { result, loading, error, run };
}
