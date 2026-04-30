import { apiFetch } from './client';
import type {
  BrowseResponse,
  MediaItem,
  SearchResponse,
  CompareResponse,
  WatchlistResponse,
  WatchlistAlgoResponse,
  WatchlistCompareResponse,
  StatsResponse,
  GraphStats,
  ColdStartJobAck,
  ColdStartJobResult,
} from './types';

export const fetchMovies = (limit: number, offset: number) =>
  apiFetch<BrowseResponse>(`/movies?limit=${limit}&offset=${offset}`);

export const fetchShows = (limit: number, offset: number) =>
  apiFetch<BrowseResponse>(`/shows?limit=${limit}&offset=${offset}`);

export const fetchMovie = (id: number) =>
  apiFetch<MediaItem>(`/movies/${id}`);

export const fetchShow = (id: number) =>
  apiFetch<MediaItem>(`/shows/${id}`);

export const searchItems = (q: string, type: string, limit = 20) =>
  apiFetch<SearchResponse>(`/search?q=${encodeURIComponent(q)}&type=${type}&limit=${limit}`);

export const fetchCompare = (id: number, k = 10) =>
  apiFetch<CompareResponse>(`/recommend/compare/${id}?k=${k}`);

export const fetchWatchlistRecs = (ids: number[], k = 10) =>
  apiFetch<WatchlistResponse>(`/recommend/watchlist?k=${k}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ids),
  });

const watchlistPost = <T>(path: string, ids: number[], k = 10) =>
  apiFetch<T>(`${path}?k=${k}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ids),
  });

export const fetchWatchlistCompare = (ids: number[], k = 10) =>
  watchlistPost<WatchlistCompareResponse>('/recommend/watchlist/compare', ids, k);

export const fetchWatchlistDirect = (ids: number[], k = 10) =>
  watchlistPost<WatchlistAlgoResponse>('/recommend/watchlist/direct', ids, k);

export const fetchWatchlistBfs = (ids: number[], k = 10) =>
  watchlistPost<WatchlistAlgoResponse>('/recommend/watchlist/bfs', ids, k);

export const fetchWatchlistPagerank = (ids: number[], k = 10) =>
  watchlistPost<WatchlistAlgoResponse>('/recommend/watchlist/pagerank', ids, k);

// ── Watchlist CRUD (authenticated) ────────────────────────────────────────────

export interface WatchlistCrudResponse {
  count: number;
  items: MediaItem[];
}

export const fetchUserWatchlist = () =>
  apiFetch<WatchlistCrudResponse>('/watchlist');

export const addToUserWatchlist = (tmdb_id: number, media_type: 'movie' | 'show') =>
  apiFetch<{ status: string }>('/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tmdb_id, media_type }),
  });

export const removeFromUserWatchlist = (tmdb_id: number, media_type: 'movie' | 'show') =>
  apiFetch<{ status: string }>(`/watchlist/${tmdb_id}?media_type=${media_type}`, {
    method: 'DELETE',
  });

export const clearUserWatchlist = () =>
  apiFetch<{ status: string }>('/watchlist', { method: 'DELETE' });

// ── Stats ──────────���───────────────────────��──────────────────────────────────

export const fetchStats = () =>
  apiFetch<StatsResponse>('/stats');

export const fetchGraphStats = () =>
  apiFetch<GraphStats>('/graph/stats');

export interface ColdStartRequest {
  q1_media_type: string;
  q2_genres: string;
  q3_title: string;
  q4_dark: string;
  q5_familiar: string;
  k?: number;
}

export const submitColdStart = (body: ColdStartRequest) =>
  apiFetch<ColdStartJobAck>('/recommend/coldstart', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const fetchJobResult = (jobId: string) =>
  apiFetch<ColdStartJobResult>(`/jobs/${jobId}`);
