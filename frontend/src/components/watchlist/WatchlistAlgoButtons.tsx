interface Props {
  loading: boolean;
  onCompare: () => void;
  onDirect: () => void;
  onBfs: () => void;
  onPagerank: () => void;
}

export function WatchlistAlgoButtons({ loading, onCompare, onDirect, onBfs, onPagerank }: Props) {
  return (
    <div className="flex flex-wrap gap-3 justify-center">
      <button
        onClick={onCompare}
        disabled={loading}
        className="px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-semibold text-white transition disabled:opacity-50"
      >
        {loading ? 'Running…' : 'Compare All Algorithms'}
      </button>
      <button
        onClick={onDirect}
        disabled={loading}
        className="px-4 py-3 bg-surface-card border border-surface-border hover:bg-surface-raised rounded-xl text-sm font-medium text-text-primary transition disabled:opacity-50"
      >
        Direct
      </button>
      <button
        onClick={onBfs}
        disabled={loading}
        className="px-4 py-3 bg-surface-card border border-surface-border hover:bg-surface-raised rounded-xl text-sm font-medium text-text-primary transition disabled:opacity-50"
      >
        BFS
      </button>
      <button
        onClick={onPagerank}
        disabled={loading}
        className="px-4 py-3 bg-surface-card border border-surface-border hover:bg-surface-raised rounded-xl text-sm font-medium text-text-primary transition disabled:opacity-50"
      >
        PageRank
      </button>
    </div>
  );
}
