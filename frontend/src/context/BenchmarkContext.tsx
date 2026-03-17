import { createContext, useContext, useState } from 'react';
import type { BenchmarkTimings } from '../api/types';

interface BenchmarkContextValue {
  timings: BenchmarkTimings | null;
  setTimings: (t: BenchmarkTimings) => void;
}

const BenchmarkContext = createContext<BenchmarkContextValue | null>(null);

export function BenchmarkProvider({ children }: { children: React.ReactNode }) {
  const [timings, setTimings] = useState<BenchmarkTimings | null>(null);
  return (
    <BenchmarkContext.Provider value={{ timings, setTimings }}>
      {children}
    </BenchmarkContext.Provider>
  );
}

export function useBenchmarkContext(): BenchmarkContextValue {
  const ctx = useContext(BenchmarkContext);
  if (!ctx) throw new Error('useBenchmarkContext must be used inside BenchmarkProvider');
  return ctx;
}
