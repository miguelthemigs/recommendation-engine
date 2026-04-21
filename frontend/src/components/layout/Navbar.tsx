import { NavLink, useNavigate } from 'react-router-dom';
import { WatchlistCounter } from '../watchlist/WatchlistCounter';
import { useAuth } from '../../context/AuthContext';

const links = [
  { to: '/movies',   label: 'Movies' },
  { to: '/shows',    label: 'Shows' },
  { to: '/search',   label: 'Search' },
  { to: '/discover', label: 'Discover' },
  { to: '/stats',    label: 'Stats' },
];

export function Navbar() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    navigate('/movies');
  };

  return (
    <nav className="sticky top-0 z-50 bg-surface/90 backdrop-blur border-b border-surface-border">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <NavLink to="/movies" className="text-accent font-bold text-lg tracking-tight">
          Rec Engine
        </NavLink>
        <div className="flex items-center gap-1">
          {links.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-lg text-sm transition ${
                  isActive
                    ? 'text-text-primary bg-surface-raised'
                    : 'text-text-secondary hover:text-text-primary hover:bg-surface-raised'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
          <NavLink
            to="/watchlist"
            className={({ isActive }) =>
              `flex items-center px-3 py-1.5 rounded-lg text-sm transition ${
                isActive
                  ? 'text-text-primary bg-surface-raised'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-raised'
              }`
            }
          >
            Watchlist
            <WatchlistCounter />
          </NavLink>

          <span className="mx-1 h-5 w-px bg-surface-border" />

          {user ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted truncate max-w-[140px]">
                {user.email}
              </span>
              <button
                onClick={handleSignOut}
                className="px-3 py-1.5 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-surface-raised transition"
              >
                Sign out
              </button>
            </div>
          ) : (
            <NavLink
              to="/login"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? 'text-accent bg-accent/10'
                    : 'text-accent hover:bg-accent/10'
                }`
              }
            >
              Sign in
            </NavLink>
          )}
        </div>
      </div>
    </nav>
  );
}
