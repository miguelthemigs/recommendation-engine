import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { WatchlistProvider } from './context/WatchlistContext';
import { BenchmarkProvider } from './context/BenchmarkContext';
import { ColdStartProvider } from './context/ColdStartContext';
import { App } from './App';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <BenchmarkProvider>
          <ColdStartProvider>
            <WatchlistProvider>
              <App />
            </WatchlistProvider>
          </ColdStartProvider>
        </BenchmarkProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>
);
