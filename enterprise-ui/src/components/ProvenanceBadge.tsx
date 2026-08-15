/**
 * ProvenanceBadge — visual label for EVOSIA evidence provenance.
 *
 * Three provenance classes, never conflated:
 *   LIVE_EVOSIA_EVIDENCE — data returned by an EVOSIA API endpoint.
 *   GEMINI_EXPLANATION   — server-side Gemini-generated plain-language
 *                          explanation. Must never impersonate evidence.
 *   DEMO_DATA            — synthetic fixture used only in explicit demo mode.
 *
 * Gemini may explain. EVOSIA decides.
 */

import './ProvenanceBadge.css';

export type Provenance = 'live' | 'gemini' | 'demo';

export default function ProvenanceBadge({ provenance }: { provenance: Provenance }) {
  const cls =
    provenance === 'live'
      ? 'provenance-badge provenance-live'
      : provenance === 'gemini'
      ? 'provenance-badge provenance-gemini'
      : 'provenance-badge provenance-demo';

  const label =
    provenance === 'live'
      ? 'Live EVOSIA evidence'
      : provenance === 'gemini'
      ? 'AI explanation'
      : 'Demo data';

  return <span className={cls}>{label}</span>;
}
