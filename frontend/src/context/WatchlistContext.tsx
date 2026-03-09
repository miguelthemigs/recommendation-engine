import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { MediaItem } from '../api/types';

interface WatchlistContextType {
  items: MediaItem[];
  add: (item: MediaItem) => void;
  remove: (id: number) => void;
  toggle: (item: MediaItem) => void;
  has: (id: number) => boolean;
  clear: () => void;
}

const WatchlistContext = createContext<WatchlistContextType | null>(null);

const STORAGE_KEY = 'rec-engine-watchlist';

export function WatchlistProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<MediaItem[]>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as MediaItem[]) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [items]);

  const add = (item: MediaItem) =>
    setItems(prev => prev.some(i => i.id === item.id) ? prev : [...prev, item]);

  const remove = (id: number) =>
    setItems(prev => prev.filter(i => i.id !== id));

  const toggle = (item: MediaItem) =>
    items.some(i => i.id === item.id) ? remove(item.id) : add(item);

  const has = (id: number) => items.some(i => i.id === id);

  const clear = () => setItems([]);

  return (
    <WatchlistContext.Provider value={{ items, add, remove, toggle, has, clear }}>
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const ctx = useContext(WatchlistContext);
  if (!ctx) throw new Error('useWatchlist must be used inside WatchlistProvider');
  return ctx;
}
