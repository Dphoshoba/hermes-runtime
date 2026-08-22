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

const needsAttentionPayload = [
  {
    finding_id: 'f1',
    title: 'Hardcoded credential',
    plain_title: 'A hardcoded credential was found',
    severity: 'high',
    category: 'security',
    why_it_matters: 'This may involve sensitive information or access controls.',
    current_classification: 'ACTIONABLE',
    classification_label: 'Actionable',
    has_human_decision: true,
    technical: { module: 'src/config.py', evidence_references: ['line 3'], gate_state: 'open', adjudication_id: 'a1' },
  },
]

const missionsPayload = [
  {
    mission_id: 'm1',
    title: 'Replace hardcoded credential',
    plain_title: 'Replace hardcoded credential with environment variable',
    what: 'Replace the hardcoded credential with an environment variable lookup',
    why: 'To avoid storing secrets in code',
    benefit: 'Improves security',
    risk: 'Low',
    scope: 'src/config.py',
    validation: 'Run tests',
    rollback: 'Revert the change',
    authority_consequence: 'Permits EVOSIA to prepare a change in an isolated workspace',
    status: 'DRAFT',
    status_label: 'Draft',
    originating_finding: 'Hardcoded credential',
    human_adjudication_ref: 'a1',
    technical: {},
  },
]

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

describe('M8-P1-003: review scope visibility', () => {
  it('shows what EVOSIA inspected on the summary', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/what evosia inspected/i)).toBeTruthy()
    })
    expect(screen.getAllByText(/sample-service/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/observations examined/i)).toBeTruthy()
    expect(screen.getAllByText(/0 changes made/i).length).toBeGreaterThan(0)
  })

  it('does not claim nonexistent scan coverage', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })
    // Must not claim specific folder/file coverage that backend doesn't record
    expect(screen.queryByText(/folders inspected/i)).toBeFalsy()
    expect(screen.queryByText(/files inspected/i)).toBeFalsy()
  })

  it('exposes source/module in plain language on findings', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(needsAttentionPayload))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })

    // Navigate to Needs your attention
    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /review items worth discussing/i }))
    })

    await waitFor(() => {
      expect(screen.getByText(/found in:/i)).toBeTruthy()
    })
    expect(screen.getAllByText(/src\/config\.py/i).length).toBeGreaterThan(0)
  })
})

describe('M8-P1-006: finding → mission bridge', () => {
  it('proposed work identifies the concern it responds to', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(missionsPayload))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })

    // Navigate to Proposed work
    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /view proposed work/i }))
    })

    await waitFor(() => {
      expect(screen.getByText(/this proposed work responds to/i)).toBeTruthy()
    })
    expect(screen.getAllByText(/hardcoded credential/i).length).toBeGreaterThan(0)
  })
})

describe('M8-P1-005: no dead controls', () => {
  it('"Not now" removes the item from view and shows acknowledgement', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(missionsPayload))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })

    // Navigate to Proposed work
    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /view proposed work/i }))
    })

    await waitFor(() => {
      expect(screen.getByText(/replace hardcoded credential with environment variable/i)).toBeTruthy()
    })

    // Click "Not now"
    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /not now/i }))
    })

    // Item should be removed from view and a deferred notice shown
    await waitFor(() => {
      expect(screen.queryByText(/replace hardcoded credential with environment variable/i)).toBeFalsy()
    })
    expect(screen.getByText(/1 item set aside/i)).toBeTruthy()
    // "Show again" control should restore
    expect(screen.getAllByRole('button', { name: /show again/i }).length).toBeGreaterThan(0)
  })

  it('"Not now" does NOT approve, prepare, or execute work', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(missionsPayload))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /view proposed work/i }))
    })

    await waitFor(() => {
      expect(screen.getByText(/replace hardcoded credential with environment variable/i)).toBeTruthy()
    })

    // Count calls to approve/prepare endpoints before clicking "Not now"
    const callsBefore = mockFetch.mock.calls.filter((c) => {
      const url = c[0]?.toString() || ''
      return url.includes('approve-preparation') || url.includes('/prepare')
    }).length

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /not now/i }))
    })

    const callsAfter = mockFetch.mock.calls.filter((c) => {
      const url = c[0]?.toString() || ''
      return url.includes('approve-preparation') || url.includes('/prepare')
    }).length

    // No new approve/prepare calls were made
    expect(callsAfter).toBe(callsBefore)
  })

  it('"Needs clarification" produces observable behaviour with Gemini provenance', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(missionsPayload))
      .mockResolvedValueOnce(ok({ explanation: 'This is an AI-generated explanation of the proposed work.' }))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /view proposed work/i }))
    })

    await waitFor(() => {
      expect(screen.getByText(/replace hardcoded credential with environment variable/i)).toBeTruthy()
    })

    // Click "Needs clarification"
    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /needs clarification/i }))
    })

    // Should show clarification panel with AI-assisted provenance
    await waitFor(() => {
      expect(screen.getAllByText(/ai-assisted/i).length).toBeGreaterThan(0)
    })
    expect(screen.getByText(/not live evosia evidence/i)).toBeTruthy()
    expect(screen.getByText(/this is an ai-generated explanation/i)).toBeTruthy()
  })

  it('"Needs clarification" shows visible fallback when Gemini unavailable', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(missionsPayload))
      .mockResolvedValueOnce(err(503, { detail: 'Gemini unavailable' }))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /view proposed work/i }))
    })

    await waitFor(() => {
      expect(screen.getByText(/replace hardcoded credential with environment variable/i)).toBeTruthy()
    })

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /needs clarification/i }))
    })

    // Should show fallback message
    await waitFor(() => {
      expect(screen.getByText(/unable to provide an explanation/i)).toBeTruthy()
    })
  })

  it('no Guided Mode button silently does nothing', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(missionsPayload))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /view proposed work/i }))
    })

    await waitFor(() => {
      expect(screen.getByText(/replace hardcoded credential with environment variable/i)).toBeTruthy()
    })

    // Every button in the mission card should have a handler
    const buttons = screen.getAllByRole('button')
    for (const btn of buttons) {
      expect(btn).not.toBeDisabled()
      expect(btn.onclick).not.toBeNull()
    }
  })

  it('Prepared ≠ Executed remains intact throughout the journey', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
    renderGuided()

    await completeOnboarding()

    await waitFor(() => {
      expect(screen.getByText(/i reviewed your project/i)).toBeTruthy()
    })

    // Summary shows 0 changes made
    expect(screen.getAllByText(/0 changes made/i).length).toBeGreaterThan(0)
  })
})
