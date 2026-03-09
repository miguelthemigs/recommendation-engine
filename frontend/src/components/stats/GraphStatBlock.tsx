import type { GraphIndexStats } from '../../api/types';
import { StatCard } from './StatCard';

interface Props {
  title: string;
  stats: GraphIndexStats;
}

export function GraphStatBlock({ title, stats }: Props) {
  if (stats.status !== 'ready' || stats.nodes === undefined) {
    return (
      <div className="space-y-3">
        <h3 className="font-semibold text-text-primary">{title}</h3>
        <p className="text-sm text-text-muted">{stats.status}</p>
      </div>
    );
  }

  const avgDegree = stats.nodes > 0 ? ((stats.edges ?? 0) * 2) / stats.nodes : 0;

  return (
    <div className="space-y-3">
      <h3 className="font-semibold text-text-primary">{title}</h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Nodes" value={stats.nodes.toLocaleString()} />
        <StatCard label="Edges" value={(stats.edges ?? 0).toLocaleString()} />
        <StatCard label="Avg degree" value={avgDegree.toFixed(1)} />
        <StatCard label="Build time" value={`${((stats.build_time_seconds ?? 0) * 1000).toFixed(0)} ms`} />
      </div>
    </div>
  );
}
