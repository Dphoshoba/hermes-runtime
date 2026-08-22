/**
 * Build provenance for the running frontend.
 *
 * The authoritative identity is the BACKEND serving the page (it knows the
 * deployed commit). We prefer the build-time injected SHA when present and
 * fall back to asking /api/version so the footer can never disagree with the
 * API actually answering the participant.
 */
declare const __EVOSIA_BUILD_SHA__: string

let cached: string | null = null

export function buildSha(): string {
  if (cached) return cached
  try {
    if (typeof __EVOSIA_BUILD_SHA__ !== 'undefined' && __EVOSIA_BUILD_SHA__ !== 'unknown') {
      return __EVOSIA_BUILD_SHA__
    }
  } catch {
    /* constant not defined — fall through */
  }
  return 'checking…'
}

export async function resolveBuildSha(): Promise<string> {
  if (cached) return cached
  try {
    const res = await fetch('/api/version')
    const data = await res.json()
    cached = String(data.build_sha || 'unknown')
  } catch {
    cached = 'unknown'
  }
  return cached
}
