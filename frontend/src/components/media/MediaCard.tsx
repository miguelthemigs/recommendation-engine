import { Link } from 'react-router-dom';
import type { MediaItem } from '../../api/types';
import { PosterImage } from './PosterImage';
import { MediaBadge } from './MediaBadge';
import { releaseYear, cn } from '../../lib/utils';
import { useWatchlist } from '../../context/WatchlistContext';

interface Props {
  item: MediaItem;
  highlight?: boolean;
}

export function MediaCard({ item, highlight = false }: Props) {
  const { toggle, has } = useWatchlist();
  const path = item.type === 'movie' ? `/movies/${item.id}` : `/shows/${item.id}`;
  const inList = has(item.id);

  return (
    <div className={cn(
      'bg-surface-card border rounded-xl overflow-hidden hover:-translate-y-1 transition-transform group',
      highlight ? 'border-accent/40' : 'border-surface-border'
    )}>
      <Link to={path} className="block">
        <PosterImage
          posterPath={item.poster_path}
          title={item.title}
          className="w-full aspect-[2/3]"
        />
      </Link>
      <div className="p-2 space-y-1">
        <div className="flex items-start justify-between gap-1">
          <Link to={path} className="text-xs font-medium text-text-primary hover:text-accent line-clamp-2 flex-1">
            {item.title}
          </Link>
          <button
            onClick={() => toggle(item)}
            title={inList ? 'Remove from watchlist' : 'Add to watchlist'}
            className={`shrink-0 text-sm transition ${inList ? 'text-accent' : 'text-text-muted hover:text-accent'}`}
          >
            {inList ? '★' : '☆'}
          </button>
        </div>
        <div className="flex items-center gap-1.5">
          <MediaBadge type={item.type} />
          {releaseYear(item) && (
            <span className="text-xs text-text-muted">{releaseYear(item)}</span>
          )}
        </div>
      </div>
    </div>
  );
}
