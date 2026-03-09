import type { CompareResponse } from '../../api/types';
import { RecommendColumn } from './RecommendColumn';
import { OverlapBadge } from './OverlapBadge';

interface Props {
  data: CompareResponse;
}

export function ComparePanel({ data }: Props) {
  const overlapIds = new Set(data.overlap.ids);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-bold text-text-primary">Recommendations</h2>
        <OverlapBadge count={data.overlap.count} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecommendColumn
          title="Jaccard (genres/keywords/cast)"
          queryMs={data.jaccard.query_time_ms}
          items={data.jaccard.recommendations}
          overlapIds={overlapIds}
        />
        <RecommendColumn
          title="TF-IDF (overview text)"
          queryMs={data.tfidf.query_time_ms}
          items={data.tfidf.recommendations}
          overlapIds={overlapIds}
        />
      </div>
    </div>
  );
}
