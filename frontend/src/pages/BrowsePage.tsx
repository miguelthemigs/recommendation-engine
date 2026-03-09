import { useEffect } from 'react';
import { useBrowse } from '../hooks/useBrowse';
import { MediaGrid } from '../components/media/MediaGrid';
import { Spinner } from '../components/ui/Spinner';
import { ErrorMessage } from '../components/ui/ErrorMessage';
import { EmptyState } from '../components/ui/EmptyState';
import { Pagination } from '../components/ui/Pagination';

interface Props {
  type: 'movie' | 'show';
}

export function BrowsePage({ type }: Props) {
  const { data, loading, error, refetch, page, setPage, totalPages } = useBrowse(type);

  useEffect(() => { setPage(1); }, [type, setPage]);

  if (loading) return <Spinner />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;
  if (!data || data.items.length === 0) return <EmptyState />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">
          {type === 'movie' ? 'Movies' : 'TV Shows'}
          <span className="ml-2 text-sm text-text-muted font-normal">
            {data.total.toLocaleString()} total
          </span>
        </h1>
      </div>
      <MediaGrid items={data.items} />
      <Pagination page={page} totalPages={totalPages} onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
    </div>
  );
}
