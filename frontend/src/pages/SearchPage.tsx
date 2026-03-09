import { useSearchParams } from 'react-router-dom';
import { useSearch } from '../hooks/useSearch';
import { MediaGrid } from '../components/media/MediaGrid';
import { Spinner } from '../components/ui/Spinner';
import { ErrorMessage } from '../components/ui/ErrorMessage';
import { EmptyState } from '../components/ui/EmptyState';
import { TypeFilter } from '../components/ui/TypeFilter';

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const type = params.get('type') ?? 'all';

  const { results, loading, error } = useSearch(q, type);

  const setQ = (v: string) => setParams(p => { p.set('q', v); return p; });
  const setType = (v: string) => setParams(p => { p.set('type', v); return p; });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="Search movies and shows…"
          value={q}
          onChange={e => setQ(e.target.value)}
          className="flex-1 bg-surface-card border border-surface-border rounded-lg px-4 py-2.5 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
        />
        <TypeFilter value={type} onChange={setType} />
      </div>

      {loading && <Spinner />}
      {error && <ErrorMessage message={error} />}
      {!loading && !error && q && results.length === 0 && (
        <EmptyState message={`No results for "${q}"`} />
      )}
      {!loading && !error && results.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm text-text-muted">{results.length} results</p>
          <MediaGrid items={results} />
        </div>
      )}
    </div>
  );
}
