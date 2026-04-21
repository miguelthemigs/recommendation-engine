import { Routes, Route, Navigate } from 'react-router-dom';
import { PageShell } from './components/layout/PageShell';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { BrowsePage } from './pages/BrowsePage';
import { SearchPage } from './pages/SearchPage';
import { ItemDetailPage } from './pages/ItemDetailPage';
import { WatchlistPage } from './pages/WatchlistPage';
import { StatsPage } from './pages/StatsPage';
import { ColdStartPage } from './pages/ColdStartPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ImportBanner } from './components/watchlist/ImportBanner';

export function App() {
  return (
    <PageShell>
      <ImportBanner />
      <Routes>
        <Route path="/" element={<Navigate to="/movies" replace />} />
        <Route path="/movies" element={<BrowsePage type="movie" />} />
        <Route path="/shows" element={<BrowsePage type="show" />} />
        <Route path="/movies/:id" element={<ItemDetailPage type="movie" />} />
        <Route path="/shows/:id" element={<ItemDetailPage type="show" />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/watchlist"
          element={
            <ProtectedRoute>
              <WatchlistPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/discover"
          element={
            <ProtectedRoute>
              <ColdStartPage />
            </ProtectedRoute>
          }
        />
        <Route path="/stats" element={<StatsPage />} />
      </Routes>
    </PageShell>
  );
}
