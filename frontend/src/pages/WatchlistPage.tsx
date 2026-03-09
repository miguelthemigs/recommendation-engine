import { useWatchlist } from '../context/WatchlistContext';
import { useWatchlistRecs } from '../hooks/useWatchlistRecs';
import { MediaGrid } from '../components/media/MediaGrid';
import { MediaCard } from '../components/media/MediaCard';
import { Spinner } from '../components/ui/Spinner';
import { ErrorMessage } from '../components/ui/ErrorMessage';
import { EmptyState } from '../components/ui/EmptyState';
import type { MediaItem } from '../api/types';

export function WatchlistPage() {
  const { items, clear } = useWatchlist();
  const { results, loading, error, fetch } = useWatchlistRecs();

  const getRecs = () => fetch(items.map(i => i.id));

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

      <div className="flex justify-center">
        <button
          onClick={getRecs}
          disabled={loading}
          className="px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-semibold text-white transition disabled:opacity-50"
        >
          {loading ? 'Getting Recommendations…' : 'Get Recommendations'}
        </button>
      </div>

      {error && <ErrorMessage message={error} />}

      {results && results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-text-primary">Recommended for your watchlist</h2>
          <MediaGrid items={results} />
        </div>
      )}
    </div>
  );
}
