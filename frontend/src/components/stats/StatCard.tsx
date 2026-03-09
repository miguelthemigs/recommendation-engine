interface Props {
  label: string;
  value: string | number;
  sub?: string;
}

export function StatCard({ label, value, sub }: Props) {
  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-5 space-y-1">
      <p className="text-text-muted text-sm">{label}</p>
      <p className="text-3xl font-bold text-text-primary">{value}</p>
      {sub && <p className="text-xs text-text-secondary">{sub}</p>}
    </div>
  );
}
