import { useParams } from 'react-router-dom';
import { useRecommend } from '../hooks/useRecommend';
import { Spinner } from '../components/ui/Spinner';
import { ErrorMessage } from '../components/ui/ErrorMessage';
import { ComparePanel } from '../components/recommendations/ComparePanel';
import { WatchlistButton } from '../components/watchlist/WatchlistButton';
import { PosterImage } from '../components/media/PosterImage';
import { MediaBadge } from '../components/media/MediaBadge';
import { releaseYear } from '../lib/utils';

interface Props {
  type: 'movie' | 'show';
}

export function ItemDetailPage({ type: _type }: Props) {
  const { id } = useParams<{ id: string }>();
  const tmdbId = Number(id);
  const { data, loading, error, refetch } = useRecommend(tmdbId);

  if (loading) return <Spinner />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;
  if (!data) return null;

  const { item } = data;

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="flex gap-6">
        <PosterImage
          posterPath={item.poster_path}
          title={item.title}
          className="w-32 sm:w-48 aspect-[2/3] rounded-xl shrink-0"
        />
        <div className="flex-1 space-y-3">
          <div className="flex items-start gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-text-primary">{item.title}</h1>
            <MediaBadge type={item.type} />
          </div>
          <p className="text-text-muted text-sm">{releaseYear(item)}</p>
          <p className="text-text-secondary text-sm leading-relaxed line-clamp-4">{item.overview}</p>
          <div className="flex flex-wrap gap-1.5">
            {item.genres.map(g => (
              <span key={g} className="text-xs px-2 py-0.5 bg-surface-raised border border-surface-border rounded-full text-text-secondary">
                {g}
              </span>
            ))}
          </div>
          <WatchlistButton item={item} />
        </div>
      </div>

      {/* Compare Panel */}
      <ComparePanel data={data} />
    </div>
  );
}
