import { useState, useEffect } from 'react';
import { fetchStats, fetchGraphStats } from '../api/endpoints';
import type { StatsResponse, GraphStats } from '../api/types';
import { useBenchmarkContext } from '../context/BenchmarkContext';
import { useColdStartContext } from '../context/ColdStartContext';
import { StatCard } from '../components/stats/StatCard';
import { GraphStatBlock } from '../components/stats/GraphStatBlock';
import { GenreList } from '../components/stats/GenreList';
import { Spinner } from '../components/ui/Spinner';
import { ErrorMessage } from '../components/ui/ErrorMessage';

export function StatsPage() {
  const { timings } = useBenchmarkContext();
  const { lastResult: cs } = useColdStartContext();
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

      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-text-primary">Cold-Start (Discover)</h2>
        {!cs ? (
          <p className="text-sm text-text-muted">Run a Discover session to see cold-start stats.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard label="LLM time" value={`${cs.llm_time_ms.toFixed(0)} ms`} />
            <StatCard label="Query time" value={`${cs.query_time_ms.toFixed(1)} ms`} />
            <StatCard label="Input tokens" value={cs.token_cost.input_tokens.toLocaleString()} />
            <StatCard label="Output tokens" value={cs.token_cost.output_tokens.toLocaleString()} />
          </div>
        )}
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-text-primary">Watchlist Algorithm Benchmarks</h2>
        {!timings ? (
          <p className="text-sm text-text-muted">Run a watchlist comparison to see benchmark results.</p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <StatCard
                label="Direct aggregation"
                value={`${timings.direct_ms?.toFixed(2)} ms`}
                sub={timings.recorded_at ? `Last run: ${new Date(timings.recorded_at).toLocaleTimeString()}` : undefined}
              />
              <StatCard
                label="BFS depth-2"
                value={`${timings.bfs_ms?.toFixed(2)} ms`}
                sub={timings.recorded_at ? `Last run: ${new Date(timings.recorded_at).toLocaleTimeString()}` : undefined}
              />
              <StatCard
                label="Personalized PageRank"
                value={`${timings.pagerank_ms?.toFixed(2)} ms`}
                sub={timings.recorded_at ? `Last run: ${new Date(timings.recorded_at).toLocaleTimeString()}` : undefined}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
