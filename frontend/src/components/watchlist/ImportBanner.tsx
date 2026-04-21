import { useWatchlist } from '../../context/WatchlistContext';

export function ImportBanner() {
  const { importPending, acceptImport, dismissImport } = useWatchlist();

  if (!importPending) return null;

  return (
    <div className="mx-auto max-w-7xl px-4 mt-2">
      <div className="flex items-center justify-between gap-4 rounded-lg border border-accent/30 bg-accent/5 px-4 py-3">
        <p className="text-sm text-text-primary">
          You have <span className="font-semibold">{importPending.length}</span> item
          {importPending.length > 1 ? 's' : ''} in your local watchlist. Import them to your
          account?
        </p>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={acceptImport}
            className="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent/90 transition"
          >
            Import
          </button>
          <button
            onClick={dismissImport}
            className="rounded-lg border border-surface-border px-4 py-1.5 text-sm text-text-secondary hover:text-text-primary transition"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
