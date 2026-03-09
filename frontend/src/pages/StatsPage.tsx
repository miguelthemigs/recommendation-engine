import { useState, useEffect } from 'react';
import { fetchStats, fetchGraphStats } from '../api/endpoints';
import type { StatsResponse, GraphStats } from '../api/types';
import { StatCard } from '../components/stats/StatCard';
import { GraphStatBlock } from '../components/stats/GraphStatBlock';
import { GenreList } from '../components/stats/GenreList';
import { Spinner } from '../components/ui/Spinner';
import { ErrorMessage } from '../components/ui/ErrorMessage';

export function StatsPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchStats(), fetchGraphStats()])
      .then(([s, g]) => { setStats(s); setGraphStats(g); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorMessage message={error} />;
  if (!stats || !graphStats) return null;

  const allGenres = { ...stats.movie_genres, ...stats.show_genres };

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-bold text-text-primary">Dataset Stats</h1>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <StatCard label="Movies" value={stats.total_movies.toLocaleString()} />
        <StatCard label="TV Shows" value={stats.total_shows.toLocaleString()} />
        <StatCard label="Total items" value={stats.total_items.toLocaleString()} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-text-primary">Movie genres</h2>
          <GenreList genres={stats.movie_genres} />
        </div>
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-text-primary">Show genres</h2>
          <GenreList genres={stats.show_genres} />
        </div>
      </div>

      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-text-primary">Graph indexes</h2>
        <GraphStatBlock title="Jaccard similarity" stats={graphStats.jaccard} />
        <GraphStatBlock title="TF-IDF similarity" stats={graphStats.tfidf} />
      </div>
    </div>
  );
}
