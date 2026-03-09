interface Props {
  count: number;
}

export function OverlapBadge({ count }: Props) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-accent/10 border border-accent/20 rounded-full text-xs text-accent">
      <span>⬡</span>
      {count} overlap
    </span>
  );
}
