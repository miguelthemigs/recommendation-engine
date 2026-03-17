interface Props {
  count: number;
  label?: string;
}

export function OverlapBadge({ count, label }: Props) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-accent/10 border border-accent/20 rounded-full text-xs text-accent">
      <span>⬡</span>
      {label ? `${label}: ${count}` : `${count} overlap`}
    </span>
  );
}
