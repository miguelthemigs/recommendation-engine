import { useState, useEffect, useCallback } from 'react';
import { fetchMovies, fetchShows } from '../api/endpoints';
import type { BrowseResponse } from '../api/types';

const PAGE_SIZE = 20;

export function useBrowse(type: 'movie' | 'show') {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<BrowseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(() => {
    setLoading(true);
    setError(null);
    const offset = (page - 1) * PAGE_SIZE;
    const fn = type === 'movie' ? fetchMovies : fetchShows;
    fn(PAGE_SIZE, offset)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [page, type]);

  useEffect(() => { fetch(); }, [fetch]);

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return { data, loading, error, refetch: fetch, page, setPage, totalPages };
}
