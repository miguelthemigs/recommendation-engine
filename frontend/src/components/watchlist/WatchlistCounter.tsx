import { useWatchlist } from '../../context/WatchlistContext';

export function WatchlistCounter() {
  const { items } = useWatchlist();
  if (items.length === 0) return null;
  return (
    <span className="ml-1 inline-flex items-center justify-center w-5 h-5 bg-accent text-white text-xs rounded-full">
      {items.length}
    </span>
  );
}
