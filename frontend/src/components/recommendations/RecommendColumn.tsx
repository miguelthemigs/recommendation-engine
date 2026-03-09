import type { ScoredItem } from '../../api/types';
import { PosterImage } from '../media/PosterImage';
import { ScorePill } from './ScorePill';
import { cn, releaseYear } from '../../lib/utils';
import { Link } from 'react-router-dom';

interface Props {
  title: string;
  queryMs: number;
  items: ScoredItem[];
  overlapIds: Set<string>;
}

export function RecommendColumn({ title, queryMs, items, overlapIds }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-text-primary">{title}</h3>
        <span className="text-xs text-text-muted">{queryMs.toFixed(1)} ms</span>
      </div>
      <div className="space-y-2">
        {items.map((item, i) => {
          const path = item.type === 'movie' ? `/movies/${item.id}` : `/shows/${item.id}`;
          const inOverlap = overlapIds.has(String(item.id));
          return (
            <Link
              key={item.id}
              to={path}
              className={cn(
                'flex gap-3 p-2 rounded-lg border transition hover:bg-surface-raised',
                inOverlap ? 'border-accent/30 bg-accent/5' : 'border-surface-border bg-surface-card'
              )}
            >
              <span className="text-xs text-text-muted w-4 shrink-0 mt-0.5">{i + 1}</span>
              <PosterImage
                posterPath={item.poster_path}
                title={item.title}
                className="w-10 h-14 rounded shrink-0"
              />
              <div className="flex-1 min-w-0 space-y-1">
                <p className="text-xs font-medium text-text-primary line-clamp-2">{item.title}</p>
                <p className="text-xs text-text-muted">{releaseYear(item)}</p>
                <ScorePill score={item.similarity_score} />
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
