export interface MediaItem {
  id: number;
  type: 'movie' | 'show';
  title: string;
  year: number | null;
  overview: string;
  poster_path: string | null;
  popularity: number;
  genres: string[];
  keywords: string[];
  cast: string[];
}

export interface ScoredItem extends MediaItem {
  similarity_score: number;
}

export interface WatchlistRec extends MediaItem {
  aggregated_score: number;
}

export interface BrowseResponse {
  total: number;
  offset: number;
  limit: number;
  items: MediaItem[];
}

export interface SearchResponse {
  query: string;
  type: string;
  count: number;
  results: MediaItem[];
}

export interface RecommendColumn {
  algorithm: string;
  query_time_ms: number;
  recommendations: ScoredItem[];
}

export interface CompareResponse {
  item: MediaItem;
  jaccard: RecommendColumn;
  tfidf: RecommendColumn;
  overlap: { count: number; ids: string[] };
}

export interface WatchlistResponse {
  watchlist_size: number;
  recommendations: WatchlistRec[];
}

export interface GraphIndexStats {
  status: string;
  nodes?: number;
  edges?: number;
  build_time_seconds?: number;
}

export interface GraphStats {
  jaccard: GraphIndexStats;
  tfidf: GraphIndexStats;
}

export interface StatsResponse {
  total_movies: number;
  total_shows: number;
  total_items: number;
  movie_genres: Record<string, number>;
  show_genres: Record<string, number>;
}
