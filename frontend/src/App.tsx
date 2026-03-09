import { Routes, Route, Navigate } from 'react-router-dom';
import { PageShell } from './components/layout/PageShell';
import { BrowsePage } from './pages/BrowsePage';
import { SearchPage } from './pages/SearchPage';
import { ItemDetailPage } from './pages/ItemDetailPage';
import { WatchlistPage } from './pages/WatchlistPage';
import { StatsPage } from './pages/StatsPage';

export function App() {
  return (
    <PageShell>
      <Routes>
        <Route path="/" element={<Navigate to="/movies" replace />} />
        <Route path="/movies" element={<BrowsePage type="movie" />} />
        <Route path="/shows" element={<BrowsePage type="show" />} />
        <Route path="/movies/:id" element={<ItemDetailPage type="movie" />} />
        <Route path="/shows/:id" element={<ItemDetailPage type="show" />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/watchlist" element={<WatchlistPage />} />
        <Route path="/stats" element={<StatsPage />} />
      </Routes>
    </PageShell>
  );
}
