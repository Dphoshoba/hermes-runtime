import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import GuidedModePage from '../pages/GuidedModePage'
import { AuthContext } from '../App'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

function ok(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body), status: 200, headers: new Headers() } as Response
}
function err(status: number, body: unknown) {
  return { ok: false, json: () => Promise.resolve(body), status, statusText: '', headers: new Headers() } as Response
}

const summaryPayload = {
  repository_id: 'repo-1',
  repository_name: 'sample-service',
  total_findings: 4,
  needs_attention: 1,
  needs_context: 3,
  proposed_work: 1,
  important_issue: 1,
  questions_awaiting_answer: 3,
  authority_level: 1,
  authority_level_label: 'Inspection only',
  nothing_changed: true,
  headline: 'I reviewed your project. · 4 things examined · 1 worth discussing · 3 questions need your help · 1 proposed change · 0 changes made',
  status: 'ready',
}

function renderGuided() {
  return render(
    <MemoryRouter initialEntries={['/guided']}>
      <AuthContext.Provider value={{ user: { id: 'u1', name: 'Test User', email: 'test@example.com', is_active: true, is_admin: false }, login: vi.fn(), logout: vi.fn() }}>
        <GuidedModePage />
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

// Click through onboarding to reach summary
async function completeOnboarding() {
  for (let i = 0; i < 10; i++) {
    const btn = screen.queryByRole('button', { name: /review my project/i })
    if (btn) {
      await act(async () => { await userEvent.click(btn) })
      return
    }
    const next = screen.queryByRole('button', { name: /next/i })
    if (next) {
      await act(async () => { await userEvent.click(next) })
    } else {
      return
    }
  }
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

describe('GuidedMode loading lifecycle (M8-P1-001)', () => {
  it('exits loading into summary state after successful fetch', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
    renderGuided()

    // Initially shows onboarding (not indefinite spinner)
    expect(screen.getByText(/welcome to evosia/i)).toBeTruthy()

    await completeOnboarding()

    // After onboarding, summary should load
    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })
    expect(screen.queryByText(/reviewing your project/i)).toBeFalsy()
  })

  it('exits loading and shows error on failed fetch', async () => {
    mockFetch.mockResolvedValueOnce(err(500, { detail: 'Server error' }))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeTruthy()
    })
    expect(screen.queryByText(/reviewing your project/i)).toBeFalsy()
  })

  it('exits loading when API is unreachable', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeTruthy()
    })
    expect(screen.queryByText(/reviewing your project/i)).toBeFalsy()
  })
})

describe('GuidedMode first-run onboarding (M8-P1-002)', () => {
  it('shows onboarding overlay on first entry', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
    renderGuided()

    await waitFor(() => {
      expect(screen.getByText(/welcome to evosia/i)).toBeTruthy()
    })
  })

  it('communicates Prepared ≠ Executed', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
    renderGuided()

    await waitFor(() => {
      expect(screen.getByText(/welcome to evosia/i)).toBeTruthy()
    })

    // Click next to reach "What EVOSIA does" step
    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /next/i }))
    })

    await waitFor(() => {
      expect(screen.getByText(/prepared ≠ executed/i)).toBeTruthy()
    })
  })

  it('communicates that answering questions does not authorize changes', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
    renderGuided()

    await waitFor(() => {
      expect(screen.getByText(/welcome to evosia/i)).toBeTruthy()
    })

    // Click next three times to reach "Needs context" step (step 3)
    for (let i = 0; i < 3; i++) {
      await act(async () => {
        await userEvent.click(screen.getByRole('button', { name: /next/i }))
      })
    }

    await waitFor(() => {
      expect(screen.getByText(/answering a context question provides information only/i)).toBeTruthy()
    })
  })

  it('transitions to summary after onboarding complete', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })
  })

  it('Guided Mode exposes no execute/merge/deploy control', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
    renderGuided()

    await waitFor(() => {
      expect(screen.getByText(/welcome to evosia/i)).toBeTruthy()
    })

    expect(screen.queryByRole('button', { name: /execute|merge|deploy/i })).toBeFalsy()
  })
})
