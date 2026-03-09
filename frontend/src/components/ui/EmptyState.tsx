interface Props {
  message?: string;
}

export function EmptyState({ message = 'Nothing to show.' }: Props) {
  return (
    <div className="flex flex-col items-center gap-2 py-16 text-text-muted">
      <span className="text-4xl">🎬</span>
      <p className="text-sm">{message}</p>
    </div>
  );
}
