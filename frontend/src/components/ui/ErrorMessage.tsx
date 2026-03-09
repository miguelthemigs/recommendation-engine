interface Props {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: Props) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-text-secondary">
      <span className="text-accent text-4xl">⚠</span>
      <p className="text-sm">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-surface-raised border border-surface-border rounded-lg text-sm hover:bg-surface-card transition"
        >
          Retry
        </button>
      )}
    </div>
  );
}
