import { useWatchlist } from '../../context/WatchlistContext';
import type { MediaItem } from '../../api/types';

interface Props {
  item: MediaItem;
}

export function WatchlistButton({ item }: Props) {
  const { toggle, has } = useWatchlist();
  const inList = has(item.id);
  return (
    <button
      onClick={() => toggle(item)}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition ${
        inList
          ? 'bg-accent/10 border-accent text-accent hover:bg-accent/20'
          : 'bg-surface-raised border-surface-border text-text-secondary hover:text-text-primary hover:border-text-secondary'
      }`}
    >
      {inList ? '★ In Watchlist' : '☆ Add to Watchlist'}
    </button>
  );
}
