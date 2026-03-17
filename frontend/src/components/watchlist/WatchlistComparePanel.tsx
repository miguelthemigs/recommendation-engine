import type { WatchlistCompareResponse, WatchlistScoredItem, ScoredItem } from '../../api/types';
import { RecommendColumn } from '../recommendations/RecommendColumn';
import { WatchlistOverlapSummary } from './WatchlistOverlapSummary';

function toScoredItems(items: WatchlistScoredItem[]): ScoredItem[] {
  return items.map(item => ({ ...item, similarity_score: item.score }));
}

interface Props {
  data: WatchlistCompareResponse;
}

export function WatchlistComparePanel({ data }: Props) {
  const allThreeIds = new Set(data.overlap.ids_all_three);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-bold text-text-primary">Algorithm Comparison</h2>
        <WatchlistOverlapSummary overlap={data.overlap} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <RecommendColumn
          title="Direct aggregation"
          queryMs={data.direct.query_time_ms}
          items={toScoredItems(data.direct.recommendations)}
          overlapIds={allThreeIds}
        />
        <RecommendColumn
          title="BFS depth-2"
          queryMs={data.bfs.query_time_ms}
          items={toScoredItems(data.bfs.recommendations)}
          overlapIds={allThreeIds}
        />
        <RecommendColumn
          title="Personalized PageRank"
          queryMs={data.pagerank.query_time_ms}
          items={toScoredItems(data.pagerank.recommendations)}
          overlapIds={allThreeIds}
        />
      </div>
    </div>
  );
}
