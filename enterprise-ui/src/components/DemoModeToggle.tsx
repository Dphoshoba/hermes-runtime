/**
 * DemoModeToggle — explicit demo/live mode switch.
 *
 * Visible in the UI so the user can always tell which mode they are in.
 * Switching to demo is an explicit opt-in; the UI never silently enters demo mode.
 *
 * Gemini may explain. EVOSIA decides.
 */

import { useMode } from '../context/ModeContext';

export default function DemoModeToggle() {
  const { mode, toggleDemo, isOffline } = useMode();

  if (isOffline) {
    return (
      <div className="demo-toggle offline">
        <span className="demo-toggle-label">EVOSIA offline</span>
        <span className="demo-toggle-state muted">Check your connection and try again.</span>
      </div>
    );
  }

  return (
    <div className="demo-toggle">
      <span className="demo-toggle-label">Mode</span>
      <button
        className={`demo-toggle-btn ${mode === 'demo' ? 'demo-active' : ''}`}
        onClick={toggleDemo}
      >
        {mode === 'demo' ? 'Demo' : 'Live'}
      </button>
      {mode === 'demo' && (
        <span className="demo-toggle-hint muted">Demo mode — sample data only.</span>
      )}
      {mode === 'live' && (
        <span className="demo-toggle-hint muted">Live EVOSIA evidence.</span>
      )}
    </div>
  );
}
