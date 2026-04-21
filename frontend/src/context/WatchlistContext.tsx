import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { MediaItem } from '../api/types';
import { useAuth } from './AuthContext';
import {
  fetchUserWatchlist,
  addToUserWatchlist,
  removeFromUserWatchlist,
  clearUserWatchlist,
} from '../api/endpoints';

interface WatchlistContextType {
  items: MediaItem[];
  add: (item: MediaItem) => void;
  remove: (id: number) => void;
  toggle: (item: MediaItem) => void;
  has: (id: number) => boolean;
  clear: () => void;
  /** True while the initial server fetch is in progress */
  syncing: boolean;
  /** Non-null if a localStorage import prompt is pending */
  importPending: MediaItem[] | null;
  acceptImport: () => void;
  dismissImport: () => void;
}

const WatchlistContext = createContext<WatchlistContextType | null>(null);

const STORAGE_KEY = 'rec-engine-watchlist';

function readLocalStorage(): MediaItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as MediaItem[]) : [];
  } catch {
    return [];
  }
}

export function WatchlistProvider({ children }: { children: ReactNode }) {
  const { user, session } = useAuth();
  const [items, setItems] = useState<MediaItem[]>(() => (user ? [] : readLocalStorage()));
  const [syncing, setSyncing] = useState(false);
  const [importPending, setImportPending] = useState<MediaItem[] | null>(null);
  const prevUserId = useRef<string | null>(null);

  // ── Authenticated: fetch watchlist from server on login ──────────────────
  useEffect(() => {
    const token = session?.access_token ?? null;
    const userId = user?.id ?? null;

    // Skip if user didn't change
    if (userId === prevUserId.current) return;
    prevUserId.current = userId;

    if (userId && token) {
      // User just logged in and token is ready — fetch their server watchlist
      setSyncing(true);
      fetchUserWatchlist()
        .then(res => {
          setItems(res.items);

          // Check for localStorage items to import
          const local = readLocalStorage();
          if (local.length > 0) {
            // Filter out items already in the server watchlist
            const serverIds = new Set(res.items.map(i => `${i.id}-${i.type}`));
            const toImport = local.filter(i => !serverIds.has(`${i.id}-${i.type}`));
            if (toImport.length > 0) {
              setImportPending(toImport);
            }
          }
        })
        .catch(err => console.error('[watchlist] Failed to fetch:', err))
        .finally(() => setSyncing(false));
    } else if (!userId) {
      // User logged out — switch to localStorage
      setItems(readLocalStorage());
      setImportPending(null);
    }
  }, [user, session]);

  // ── Guest mode: persist to localStorage ─────────────────────────────────
  useEffect(() => {
    if (!user) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    }
  }, [items, user]);

  // ── Import handlers ─────────────────────────────────────────────────────
  const acceptImport = useCallback(async () => {
    if (!importPending) return;

    // Add each local item to the server
    for (const item of importPending) {
      try {
        await addToUserWatchlist(item.id, item.type);
      } catch (err) {
        console.error('[watchlist] import failed for', item.id, err);
      }
    }

    // Merge into current state
    setItems(prev => {
      const existing = new Set(prev.map(i => `${i.id}-${i.type}`));
      const merged = [...prev];
      for (const item of importPending) {
        if (!existing.has(`${item.id}-${item.type}`)) {
          merged.push(item);
        }
      }
      return merged;
    });

    localStorage.removeItem(STORAGE_KEY);
    setImportPending(null);
  }, [importPending]);

  const dismissImport = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setImportPending(null);
  }, []);

  // ── CRUD ────────────────────────────────────────────────────────────────
  const add = useCallback(
    (item: MediaItem) => {
      setItems(prev => (prev.some(i => i.id === item.id && i.type === item.type) ? prev : [...prev, item]));
      if (user) {
        addToUserWatchlist(item.id, item.type).catch(err =>
          console.error('[watchlist] add failed:', err),
        );
      }
    },
    [user],
  );

  const remove = useCallback(
    (id: number) => {
      const item = items.find(i => i.id === id);
      setItems(prev => prev.filter(i => i.id !== id));
      if (user && item) {
        removeFromUserWatchlist(id, item.type).catch(err =>
          console.error('[watchlist] remove failed:', err),
        );
      }
    },
    [user, items],
  );

  const toggle = useCallback(
    (item: MediaItem) => {
      if (items.some(i => i.id === item.id && i.type === item.type)) {
        remove(item.id);
      } else {
        add(item);
      }
    },
    [items, add, remove],
  );

  const has = useCallback(
    (id: number) => items.some(i => i.id === id),
    [items],
  );

  const clear = useCallback(() => {
    setItems([]);
    if (user) {
      clearUserWatchlist().catch(err =>
        console.error('[watchlist] clear failed:', err),
      );
    }
  }, [user]);

  return (
    <WatchlistContext.Provider
      value={{ items, add, remove, toggle, has, clear, syncing, importPending, acceptImport, dismissImport }}
    >
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const ctx = useContext(WatchlistContext);
  if (!ctx) throw new Error('useWatchlist must be used inside WatchlistProvider');
  return ctx;
}
