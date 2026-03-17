import { OverlapBadge } from '../recommendations/OverlapBadge';
import type { WatchlistOverlap } from '../../api/types';

interface Props {
  overlap: WatchlistOverlap;
}

export function WatchlistOverlapSummary({ overlap }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      <OverlapBadge count={overlap.all_three} label="All 3" />
      <OverlapBadge count={overlap.direct_bfs} label="Direct∩BFS" />
      <OverlapBadge count={overlap.direct_pagerank} label="Direct∩PR" />
      <OverlapBadge count={overlap.bfs_pagerank} label="BFS∩PR" />
    </div>
  );
}
