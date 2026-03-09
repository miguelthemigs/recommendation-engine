interface Props {
  type: 'movie' | 'show';
}

export function MediaBadge({ type }: Props) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
      type === 'movie'
        ? 'bg-accent/20 text-accent'
        : 'bg-blue-900/40 text-blue-400'
    }`}>
      {type === 'movie' ? 'Movie' : 'Show'}
    </span>
  );
}
