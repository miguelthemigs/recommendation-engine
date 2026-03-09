interface Props {
  page: number;
  totalPages: number;
  onPrev: () => void;
  onNext: () => void;
}

export function Pagination({ page, totalPages, onPrev, onNext }: Props) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-center gap-4 py-8">
      <button
        onClick={onPrev}
        disabled={page === 1}
        className="px-4 py-2 bg-surface-raised border border-surface-border rounded-lg text-sm disabled:opacity-40 hover:bg-surface-card transition"
      >
        ← Prev
      </button>
      <span className="text-text-secondary text-sm">
        {page} / {totalPages}
      </span>
      <button
        onClick={onNext}
        disabled={page === totalPages}
        className="px-4 py-2 bg-surface-raised border border-surface-border rounded-lg text-sm disabled:opacity-40 hover:bg-surface-card transition"
      >
        Next →
      </button>
    </div>
  );
}
