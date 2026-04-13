import { useRef, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { fetchColdStart } from '../api/endpoints';
import type { ColdStartResponse, MediaItem } from '../api/types';
import { useWatchlist } from '../context/WatchlistContext';
import { useColdStartContext, type ColdStartFormState } from '../context/ColdStartContext';
import { PosterImage } from '../components/media/PosterImage';
import { MediaBadge } from '../components/media/MediaBadge';
import { Spinner } from '../components/ui/Spinner';
import { releaseYear } from '../lib/utils';

// ─── Types ───────────────────────────────────────────────────────────────────

type DiscoverItem = MediaItem & { score?: number; isSeed: boolean };

type FormState = ColdStartFormState;

// ─── Sub-components ──────────────────────────────────────────────────────────

function OptionButton({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-sm font-medium border transition ${
        selected
          ? 'bg-accent text-white border-accent'
          : 'bg-surface-card border-surface-border text-text-secondary hover:border-accent/50 hover:text-text-primary'
      }`}
    >
      {label}
    </button>
  );
}

function TransparencyCard({ result }: { result: ColdStartResponse }) {
  const { signals, seeds, llm_time_ms, query_time_ms } = result;
  return (
    <div className="rounded-xl border border-accent/20 bg-accent/5 p-5 space-y-3">
      <h2 className="text-sm font-semibold text-accent uppercase tracking-wide">
        How we picked these
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        {signals.genres.length > 0 && (
          <div>
            <span className="text-text-muted">Genres detected: </span>
            <span className="text-text-primary">{signals.genres.join(', ')}</span>
          </div>
        )}
        {signals.mood !== 'neutral' && (
          <div>
            <span className="text-text-muted">Mood: </span>
            <span className="text-text-primary capitalize">{signals.mood}</span>
          </div>
        )}
        {signals.reference_titles.length > 0 && (
          <div>
            <span className="text-text-muted">You mentioned: </span>
            <span className="text-text-primary">{signals.reference_titles.join(', ')}</span>
          </div>
        )}
        {signals.keywords.length > 0 && (
          <div>
            <span className="text-text-muted">Keywords: </span>
            <span className="text-text-primary">{signals.keywords.join(', ')}</span>
          </div>
        )}
      </div>
      {seeds.length > 0 && (
        <p className="text-xs text-text-muted">
          Seeded from: {seeds.map(s => s.title).join(', ')} — then expanded via BFS.
        </p>
      )}
      <div className="flex gap-4 text-xs text-text-muted pt-1 border-t border-surface-border">
        <span>LLM: {llm_time_ms.toFixed(0)} ms</span>
        <span>Query: {query_time_ms.toFixed(1)} ms</span>
        <span>Tokens: {result.token_cost.input_tokens} in / {result.token_cost.output_tokens} out</span>
      </div>
    </div>
  );
}

function DiscoverItemRow({ item }: { item: DiscoverItem }) {
  const { toggle, has } = useWatchlist();
  const inList = has(item.id);
  const path = item.type === 'movie' ? `/movies/${item.id}` : `/shows/${item.id}`;

  return (
    <div className="flex gap-3 p-3 rounded-lg border border-surface-border bg-surface-card items-center">
      <Link to={path} className="shrink-0">
        <PosterImage posterPath={item.poster_path} title={item.title} className="w-10 h-14 rounded" />
      </Link>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <Link to={path} className="text-sm font-medium text-text-primary hover:text-accent line-clamp-1">
            {item.title}
          </Link>
          {item.isSeed && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-accent/15 text-accent font-medium shrink-0">
              seed
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <MediaBadge type={item.type} />
          {releaseYear(item) && (
            <span className="text-xs text-text-muted">{releaseYear(item)}</span>
          )}
          {item.score !== undefined && (
            <span className="text-xs text-text-muted">score {item.score.toFixed(3)}</span>
          )}
        </div>
      </div>
      <button
        onClick={() => toggle(item)}
        title={inList ? 'Remove from watchlist' : 'Add to watchlist'}
        className={`shrink-0 text-xl transition ${inList ? 'text-accent' : 'text-text-muted hover:text-accent'}`}
      >
        {inList ? '★' : '☆'}
      </button>
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export function ColdStartPage() {
  const navigate = useNavigate();
  const { add } = useWatchlist();
  const { lastResult, setLastResult, savedForm, setSavedForm } = useColdStartContext();
  const resultsRef = useRef<HTMLDivElement>(null);

  const [form, setForm] = useState<FormState>(savedForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ColdStartResponse | null>(lastResult);

  const set = (key: keyof FormState) => (val: string) =>
    setForm(prev => ({ ...prev, [key]: val }));

  const combinedByType = (): { movies: DiscoverItem[]; shows: DiscoverItem[] } => {
    if (!result) return { movies: [], shows: [] };
    const seedIds = new Set(result.seeds.map(s => String(s.id)));
    // Exclude titles the user mentioned (Q3 + any LLM-extracted reference titles)
    const mentioned = [
      form.q3.trim(),
      ...result.signals.reference_titles,
    ].map(t => t.toLowerCase()).filter(t => t.length > 0);
    const isUserMentioned = (title: string) => {
      const lower = title.toLowerCase();
      return mentioned.some(m => lower.includes(m) || m.includes(lower));
    };
    const all: DiscoverItem[] = [
      ...result.seeds
        .filter(s => !isUserMentioned(s.title))
        .map(s => ({ ...s, isSeed: true as const })),
      ...result.recommendations
        .filter(r => !seedIds.has(String(r.id)) && !isUserMentioned(r.title))
        .map(r => ({ ...r, score: r.score, isSeed: false as const })),
    ];
    return {
      movies: all.filter(i => i.type === 'movie').slice(0, 5),
      shows:  all.filter(i => i.type === 'show').slice(0, 5),
    };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.q1 || !form.q2 || !form.q3 || !form.q4 || !form.q5) {
      setError('Please answer all 5 questions.');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    setSavedForm(form);
    try {
      const data = await fetchColdStart({
        q1_media_type: form.q1,
        q2_genres: form.q2,
        q3_title: form.q3,
        q4_dark: form.q4,
        q5_familiar: form.q5,
        k: 30,
      });
      setResult(data);
      setLastResult(data);
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  };

  const handleAddAll = () => {
    if (!result) return;
    const { movies, shows } = combinedByType();
    [...movies, ...shows].forEach(item => add(item));
    navigate('/watchlist');
  };

  const { movies, shows } = combinedByType();

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Discover</h1>
        <p className="text-text-muted text-sm mt-1">
          Answer 5 questions and we'll build a personalised recommendation list.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Q1 */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-text-primary">
            1. Do you prefer movies, TV shows, or both?
          </label>
          <div className="flex gap-2 flex-wrap">
            {['Movies', 'TV Shows', 'Both'].map(opt => (
              <OptionButton
                key={opt}
                label={opt}
                selected={form.q1 === opt}
                onClick={() => set('q1')(opt)}
              />
            ))}
          </div>
        </div>

        {/* Q2 */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-text-primary">
            2. Which genres interest you?
          </label>
          <input
            type="text"
            placeholder="e.g. Action, Drama, Thriller, Sci-Fi"
            value={form.q2}
            onChange={e => set('q2')(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-surface-card border border-surface-border text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-accent/60"
          />
        </div>

        {/* Q3 */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-text-primary">
            3. Name a title you've enjoyed recently
          </label>
          <input
            type="text"
            placeholder="Doesn't have to be in our database"
            value={form.q3}
            onChange={e => set('q3')(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-surface-card border border-surface-border text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-accent/60"
          />
        </div>

        {/* Q4 */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-text-primary">
            4. How do you feel about dark or intense content?
          </label>
          <div className="flex gap-2 flex-wrap">
            {['Fine with it', 'Prefer lighter', 'No preference'].map(opt => (
              <OptionButton
                key={opt}
                label={opt}
                selected={form.q4 === opt}
                onClick={() => set('q4')(opt)}
              />
            ))}
          </div>
        </div>

        {/* Q5 */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-text-primary">
            5. Are you looking for something familiar or something new?
          </label>
          <div className="flex gap-2 flex-wrap">
            {['Familiar', 'Something new', 'No preference'].map(opt => (
              <OptionButton
                key={opt}
                label={opt}
                selected={form.q5 === opt}
                onClick={() => set('q5')(opt)}
              />
            ))}
          </div>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-accent hover:bg-accent-hover text-white font-semibold rounded-xl transition disabled:opacity-50"
        >
          {loading ? 'Finding recommendations…' : 'Discover'}
        </button>
      </form>

      {loading && <Spinner />}

      {result && (
        <div ref={resultsRef} className="space-y-6 pt-2">
          <TransparencyCard result={result} />

          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-text-primary">Your recommendations</h2>
            <button
              onClick={handleAddAll}
              className="px-4 py-2 bg-accent hover:bg-accent-hover text-white text-sm font-semibold rounded-lg transition"
            >
              Add all to watchlist →
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
                Top Movies
              </h3>
              {movies.length === 0
                ? <p className="text-sm text-text-muted">No movies found.</p>
                : movies.map(item => <DiscoverItemRow key={item.id} item={item} />)
              }
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
                Top Shows
              </h3>
              {shows.length === 0
                ? <p className="text-sm text-text-muted">No shows found.</p>
                : shows.map(item => <DiscoverItemRow key={item.id} item={item} />)
              }
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleAddAll}
              className="px-6 py-3 bg-accent hover:bg-accent-hover text-white font-semibold rounded-xl transition"
            >
              Add all to watchlist →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
