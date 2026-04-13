import { createContext, useContext, useState } from 'react';
import type { ColdStartResponse } from '../api/types';

export interface ColdStartFormState {
  q1: string;
  q2: string;
  q3: string;
  q4: string;
  q5: string;
}

interface ColdStartContextValue {
  lastResult: ColdStartResponse | null;
  setLastResult: (r: ColdStartResponse) => void;
  savedForm: ColdStartFormState;
  setSavedForm: (f: ColdStartFormState) => void;
}

const EMPTY_FORM: ColdStartFormState = { q1: '', q2: '', q3: '', q4: '', q5: '' };

const ColdStartContext = createContext<ColdStartContextValue | null>(null);

export function ColdStartProvider({ children }: { children: React.ReactNode }) {
  const [lastResult, setLastResult] = useState<ColdStartResponse | null>(null);
  const [savedForm, setSavedForm] = useState<ColdStartFormState>(EMPTY_FORM);
  return (
    <ColdStartContext.Provider value={{ lastResult, setLastResult, savedForm, setSavedForm }}>
      {children}
    </ColdStartContext.Provider>
  );
}

export function useColdStartContext(): ColdStartContextValue {
  const ctx = useContext(ColdStartContext);
  if (!ctx) throw new Error('useColdStartContext must be used inside ColdStartProvider');
  return ctx;
}
