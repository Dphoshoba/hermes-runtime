/**
 * ModeContext — app-wide demo/live mode + offline state.
 *
 * Three modes:
 *   LIVE_MODE    — default. All data from EVOSIA API. Provenance: LIVE_EVOSIA_EVIDENCE.
 *   DEMO_MODE    — explicit. Synthetic fixtures, labeled DEMO_DATA. No live API data.
 *   OFFLINE      — API unreachable while in live mode. Explicit error state.
 *
 * The UI must never silently fall back from LIVE_MODE to DEMO_DATA when the API is
 * unreachable. Demo data is only available when the user explicitly opts into demo mode.
 *
 * Gemini may explain. EVOSIA decides.
 */

import { createContext, useContext, useState, useCallback, useMemo, ReactNode } from 'react';
import useApiReachability from '../hooks/useApiReachability';

export type AppMode = 'live' | 'demo' | 'offline';

interface ModeContextValue {
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  toggleDemo: () => void;
  isLive: boolean;
  isDemo: boolean;
  isOffline: boolean;
}

const ModeContext = createContext<ModeContextValue>({
  mode: 'live',
  setMode: () => {},
  toggleDemo: () => {},
  isLive: false,
  isDemo: false,
  isOffline: false,
});

export function ModeProvider({ children }: { children: ReactNode }) {
  const reachability = useApiReachability();
  const [mode, setModeRaw] = useState<AppMode>('live');

  const setMode = useCallback((m: AppMode) => {
    // When the user explicitly picks demo, stay in demo regardless of reachability.
    // When the user picks live, let reachability override to offline.
    setModeRaw(m);
  }, []);

  const toggleDemo = useCallback(() => {
    setModeRaw((m) => (m === 'demo' ? 'live' : 'demo'));
  }, []);

  // If the user is in live mode and the API is unreachable, surface OFFLINE.
  // This does NOT silently switch to demo — it shows an offline error state.
  const effectiveMode = useMemo(() => {
    if (mode === 'demo') return 'demo';
    if (mode === 'live' && !reachability.reachable && !reachability.checking) return 'offline';
    return mode;
  }, [mode, reachability.reachable, reachability.checking]);

  const value = useMemo<ModeContextValue>(() => ({
    mode: effectiveMode,
    setMode,
    toggleDemo,
    isLive: effectiveMode === 'live',
    isDemo: effectiveMode === 'demo',
    isOffline: effectiveMode === 'offline',
  }), [effectiveMode, setMode, toggleDemo]);

  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export function useMode() {
  return useContext(ModeContext);
}