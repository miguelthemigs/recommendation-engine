interface Props {
  genres: Record<string, number>;
}

export function GenreList({ genres }: Props) {
  const sorted = Object.entries(genres).sort((a, b) => b[1] - a[1]).slice(0, 12);
  const max = sorted[0]?.[1] ?? 1;
  return (
    <div className="space-y-2">
      {sorted.map(([genre, count]) => (
        <div key={genre} className="flex items-center gap-3">
          <span className="text-sm text-text-secondary w-32 shrink-0 truncate">{genre}</span>
          <div className="flex-1 bg-surface-raised rounded-full h-2">
            <div
              className="bg-accent h-2 rounded-full"
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
          <span className="text-xs text-text-muted w-8 text-right">{count}</span>
        </div>
      ))}
    </div>
  );
}
