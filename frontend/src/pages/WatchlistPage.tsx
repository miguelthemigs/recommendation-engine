import { useState } from 'react';
import { useWatchlist } from '../context/WatchlistContext';
import { useWatchlistCompare } from '../hooks/useWatchlistCompare';
import { useWatchlistAlgo } from '../hooks/useWatchlistAlgo';
import { fetchWatchlistDirect, fetchWatchlistBfs, fetchWatchlistPagerank } from '../api/endpoints';
import { WatchlistAlgoButtons } from '../components/watchlist/WatchlistAlgoButtons';
import { WatchlistComparePanel } from '../components/watchlist/WatchlistComparePanel';
import { RecommendColumn } from '../components/recommendations/RecommendColumn';
import { MediaCard } from '../components/media/MediaCard';
import { Spinner } from '../components/ui/Spinner';
import { ErrorMessage } from '../components/ui/ErrorMessage';
import { EmptyState } from '../components/ui/EmptyState';
import type { MediaItem, WatchlistScoredItem, ScoredItem } from '../api/types';

type Mode = 'compare' | 'direct' | 'bfs' | 'pagerank' | null;

function toScoredItems(items: WatchlistScoredItem[]): ScoredItem[] {
  return items.map(item => ({ ...item, similarity_score: item.score }));
}

export function WatchlistPage() {
  const { items, clear } = useWatchlist();
  const [mode, setMode] = useState<Mode>(null);

  const compare = useWatchlistCompare();
  const direct  = useWatchlistAlgo(fetchWatchlistDirect);
  const bfs     = useWatchlistAlgo(fetchWatchlistBfs);
  const pagerank = useWatchlistAlgo(fetchWatchlistPagerank);

  const loading = compare.loading || direct.loading || bfs.loading || pagerank.loading;
  const ids = items.map(i => i.id);

  const handleCompare = () => { setMode('compare'); compare.run(ids); };
  const handleDirect  = () => { setMode('direct');  direct.run(ids); };
  const handleBfs     = () => { setMode('bfs');     bfs.run(ids); };
  const handlePagerank = () => { setMode('pagerank'); pagerank.run(ids); };

  const activeError =
    mode === 'compare'  ? compare.error  :
    mode === 'direct'   ? direct.error   :
    mode === 'bfs'      ? bfs.error      :
    mode === 'pagerank' ? pagerank.error  : null;

  if (items.length === 0) {
    return <EmptyState message="Your watchlist is empty. Add some movies or shows first." />;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">
          Watchlist
          <span className="ml-2 text-sm text-text-muted font-normal">{items.length} items</span>
        </h1>
        <button
          onClick={clear}
          className="text-xs text-text-muted hover:text-accent transition"
        >
          Clear all
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {items.map((item: MediaItem) => (
          <MediaCard key={item.id} item={item} />
        ))}
      </div>

      <WatchlistAlgoButtons
        loading={loading}
        onCompare={handleCompare}
        onDirect={handleDirect}
        onBfs={handleBfs}
        onPagerank={handlePagerank}
      />

      {loading && <Spinner />}
      {activeError && <ErrorMessage message={activeError} />}

      {mode === 'compare' && compare.result && (
        <WatchlistComparePanel data={compare.result} />
      )}

      {mode === 'direct' && direct.result && (
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-text-primary">Direct Aggregation</h2>
          <RecommendColumn
            title="Direct (genres/keywords/cast)"
            queryMs={direct.result.query_time_ms}
            items={toScoredItems(direct.result.recommendations)}
            overlapIds={new Set()}
          />
        </div>
      )}

      {mode === 'bfs' && bfs.result && (
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-text-primary">BFS Depth-2</h2>
          <RecommendColumn
            title="BFS depth-2"
            queryMs={bfs.result.query_time_ms}
            items={toScoredItems(bfs.result.recommendations)}
            overlapIds={new Set()}
          />
        </div>
      )}

      {mode === 'pagerank' && pagerank.result && (
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-text-primary">Personalized PageRank</h2>
          <RecommendColumn
            title="PageRank"
            queryMs={pagerank.result.query_time_ms}
            items={toScoredItems(pagerank.result.recommendations)}
            overlapIds={new Set()}
          />
        </div>
      )}
    </div>
  );
}
