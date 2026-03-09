import { apiFetch } from './client';
import type {
  BrowseResponse,
  MediaItem,
  SearchResponse,
  CompareResponse,
  WatchlistResponse,
  StatsResponse,
  GraphStats,
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

export const fetchStats = () =>
  apiFetch<StatsResponse>('/stats');

export const fetchGraphStats = () =>
  apiFetch<GraphStats>('/graph/stats');
