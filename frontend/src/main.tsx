import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { WatchlistProvider } from './context/WatchlistContext';
import { BenchmarkProvider } from './context/BenchmarkContext';
import { App } from './App';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <BenchmarkProvider>
        <WatchlistProvider>
          <App />
        </WatchlistProvider>
      </BenchmarkProvider>
    </BrowserRouter>
  </StrictMode>
);
