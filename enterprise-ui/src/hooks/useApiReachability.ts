/**
 * useApiReachability — detects whether the EVOSIA API is reachable.
 *
 * Returns { reachable: boolean, lastError: string | null, check: () => Promise<void> }.
 *
 * Used by the ModeContext to decide whether the UI is in LIVE_MODE (API reachable)
 * or OFFLINE state (API unreachable). When offline in live mode, the UI shows an
 * explicit error state — it must NOT silently fall back to DEMO_DATA.
 *
 * Gemini may explain. EVOSIA decides.
 */

import { useState, useCallback, useEffect } from 'react';

export interface ReachabilityState {
  reachable: boolean;
  lastError: string | null;
  checking: boolean;
}

export default function useApiReachability(): ReachabilityState & { check: () => Promise<void> } {
  const [state, setState] = useState<ReachabilityState>({
    reachable: true,
    lastError: null,
    checking: true,
  });

  const check = useCallback(async () => {
    setState((s) => ({ ...s, checking: true, lastError: null }));
    try {
      const res = await fetch('/api/health', {
        method: 'GET',
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      });
      if (res.ok) {
        setState({ reachable: true, lastError: null, checking: false });
      } else {
        const body = await res.json().catch(() => ({}));
        setState({
          reachable: false,
          lastError: (body as { detail?: string }).detail || `HTTP ${res.status}`,
          checking: false,
        });
      }
    } catch (err) {
      setState({
        reachable: false,
        lastError: err instanceof Error ? err.message : 'API unreachable',
        checking: false,
      });
    }
  }, []);

  // Initial check on mount.
  useEffect(() => {
    check();
  }, [check]);

  return { ...state, check };
}
