/**
 * Build provenance for the running frontend.
 * __EVOSIA_BUILD_SHA__ is injected at build time by Vite (vite.config.ts).
 */
declare const __EVOSIA_BUILD_SHA__: string

export function buildSha(): string {
  try {
    return typeof __EVOSIA_BUILD_SHA__ !== 'undefined' ? __EVOSIA_BUILD_SHA__ : 'unknown'
  } catch {
    return 'unknown'
  }
}
