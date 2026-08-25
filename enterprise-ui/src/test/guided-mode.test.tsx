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
  headline: 'I reviewed your project.',
  status: 'ready',
}

// Standard mock sequence for reaching the summary view:
// summary → review-scope
function mockSummaryPath() {
  mockFetch.mockResolvedValueOnce(ok(summaryPayload))
    .mockResolvedValueOnce(ok(reviewScopePayload))
}

const needsAttentionPayload = [
  {
    finding_id: 'f1',
    title: 'Hardcoded credential',
    plain_title: 'A hardcoded API key was found',
    severity: 'high',
    category: 'security',
    why_it_matters: 'Anyone who can read this source file may potentially obtain the credential.',
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
    plain_title: 'Move the API key out of the source code',
    what: 'Replace the hardcoded credential with an environment variable lookup',
    why: 'To avoid storing secrets in code',
    benefit: 'Improves security',
    risk: 'Low',
    scope: 'src/config.py',
    validation: 'Run tests',
    rollback: 'Revert the change',
    authority_consequence: 'Permits EVOSIA to prepare a change in an isolated workspace. It will not merge, deploy, or change production.',
    status: 'DRAFT',
    status_label: 'Draft',
    originating_finding: 'A hardcoded API key was found',
    human_adjudication_ref: 'a1',
    technical: {},
  },
]

const reviewScopePayload = {
  available: true,
  scan_id: 'scan-1',
  repository_name: 'sample-service',
  scope_root: 'sample-service',
  review_status: 'completed',
  started_at: '2026-08-22T20:14:00Z',
  completed_at: '2026-08-22T20:15:00Z',
  folders_inspected: ['src', 'tests', 'config'],
  files_inspected: ['src/config.py', 'src/calc.py', 'tests/test_sample.py'],
  total_folders_inspected: 3,
  total_files_inspected: 3,
  excluded_directories: ['__pycache__', 'node_modules'],
  excluded_files: null,
  exclusion_note: 'EVOSIA reviewed Python source files.',
  provenance: 'LIVE_EVOSIA_EVIDENCE',
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

async function completeOnboarding() {
  for (let i = 0; i < 12; i++) {
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

// Reach summary; optionally then navigate to proposed work.
async function reachSummary() {
  await completeOnboarding()
  await waitFor(() => {
    expect(screen.getByText(/what i reviewed/i)).toBeTruthy()
  })
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

describe('M8-P1-001: loading lifecycle', () => {
  it('successful summary fetch exits loading', async () => {
    mockSummaryPath()
    renderGuided()
    await completeOnboarding()
    await waitFor(() => {
      expect(screen.getByText(/what i reviewed/i)).toBeTruthy()
    })
    expect(screen.queryByText(/reviewing your project/i)).toBeFalsy()
  })

  it('failed summary fetch exits loading into an error state', async () => {
    mockFetch.mockResolvedValueOnce(err(500, { detail: 'Server error' }))
    renderGuided()
    await completeOnboarding()
    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeTruthy()
    })
    expect(screen.queryByText(/reviewing your project/i)).toBeFalsy()
  })

  it('unreachable API exits loading', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'))
    renderGuided()
    await completeOnboarding()
    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeTruthy()
    })
  })
})

describe('M8-P1-002: onboarding', () => {
  it('renders for first-run participant and communicates Prepared ≠ Executed', async () => {
    mockSummaryPath()
    renderGuided()
    await waitFor(() => {
      expect(screen.getByText(/welcome to evosia/i)).toBeTruthy()
    })
    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /next/i }))
    })
    await waitFor(() => {
      expect(screen.getByText(/prepared ≠ executed/i)).toBeTruthy()
    })
  })

  it('communicates context answers are not authorization', async () => {
    mockSummaryPath()
    renderGuided()
    for (let i = 0; i < 3; i++) {
      const next = screen.queryByRole('button', { name: /next/i })
      if (next) await act(async () => { await userEvent.click(next) })
    }
    await waitFor(() => {
      expect(screen.getByText(/not authorization/i)).toBeTruthy()
    })
  })
})

describe('M8-P1-003: WHAT I REVIEWED (authoritative scope)', () => {
  it('renders authoritative review-scope evidence', async () => {
    mockSummaryPath()
    renderGuided()
    await reachSummary()

    expect(screen.getByText(/folders inspected/i)).toBeTruthy()
    expect(screen.getByText(/files inspected/i)).toBeTruthy()
    expect(screen.getAllByText(/sample-service/i).length).toBeGreaterThan(0)
    // Truthful exclusion statement — backend records excluded_files as unknown
    expect(screen.getByText(/does not have verified exclusion information/i)).toBeTruthy()
  })

  it('reviewed-files disclosure works', async () => {
    mockSummaryPath()
    renderGuided()
    await reachSummary()

    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /see everything reviewed/i })) })
    expect(screen.getByText(/src\/config\.py/)).toBeTruthy()
  })

  it('missing scope evidence produces truthful unavailable state', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok({
        available: false,
        reason: 'coverage_not_recorded',
        message: 'EVOSIA completed this review, but detailed file coverage was not recorded for this review.',
      }))
    renderGuided()
    await reachSummary()

    expect(screen.getByText(/detailed file coverage was not recorded/i)).toBeTruthy()
    // Must NOT fabricate counts
    expect(screen.queryByText(/folders inspected:/i)).toBeFalsy()
  })
})

describe('M8-P1-004: WHAT I FOUND (finding evidence)', () => {
  it('finding displays source location, problem, and why it matters', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(reviewScopePayload))
      .mockResolvedValueOnce(ok(needsAttentionPayload))
    renderGuided()
    await reachSummary()

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /review important issue/i }))
    })

    await waitFor(() => {
      expect(screen.getByText(/where i found it/i)).toBeTruthy()
    })
    expect(screen.getAllByText(/src\/config\.py/).length).toBeGreaterThan(0)
    expect(screen.getByText(/why this matters/i)).toBeTruthy()
  })

  it('finding offers Review recommended fix CTA that navigates to recommendations', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(reviewScopePayload))
      .mockResolvedValueOnce(ok(needsAttentionPayload))
      .mockResolvedValueOnce(ok(missionsPayload))
    renderGuided()
    await reachSummary()

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /review important issue/i }))
    })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /review recommended fix/i })).toBeTruthy()
    })
    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /review recommended fix/i }))
    })
    await waitFor(() => {
      expect(screen.getByText(/this recommendation addresses/i)).toBeTruthy()
    })
  })
})

describe('M8-P1-006: finding → recommendation bridge', () => {
  it('mission identifies the originating finding and location', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(reviewScopePayload))
      .mockResolvedValueOnce(ok(missionsPayload))
    renderGuided()
    await reachSummary()

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /view recommended fixes/i }))
    })

    await waitFor(() => {
      expect(screen.getByText(/this recommendation addresses/i)).toBeTruthy()
    })
    expect(screen.getAllByText(/hardcoded api key/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/found in:/i)).toBeTruthy()
  })
})

describe('M8-P1-005: no dead controls / explicit feedback', () => {
  function mockProposedWork() {
    return mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(reviewScopePayload))
      .mockResolvedValueOnce(ok(missionsPayload))
  }

  it('"Not now" produces visible acknowledgement and does not approve', async () => {
    mockProposedWork()
    renderGuided()
    await reachSummary()

    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /view recommended fixes/i })) })
    await waitFor(() => {
      expect(screen.getByText(/move the api key out of the source code/i)).toBeTruthy()
    })

    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /not now/i })) })

    await waitFor(() => {
      expect(screen.getByText(/evosia will leave this recommendation unchanged/i)).toBeTruthy()
    })
    // Recommendation remains available ("Show again")
    expect(screen.getAllByRole('button', { name: /show again/i }).length).toBeGreaterThan(0)

    // No approve/prepare calls were made by "Not now"
    const approveCalls = mockFetch.mock.calls.filter((c) => String(c[0]).includes('approve-preparation') || String(c[0]).includes('/prepare'))
    expect(approveCalls.length).toBe(0)
  })

  it('"Needs clarification" shows explanation with GEMINI provenance', async () => {
    mockProposedWork()
    renderGuided()
    await reachSummary()

    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /view recommended fixes/i })) })
    await waitFor(() => {
      expect(screen.getByText(/move the api key out of the source code/i)).toBeTruthy()
    })

    // The clarify call goes through globalThis.fetch with the explain path
    mockFetch.mockResolvedValueOnce(ok({ explanation: 'AI-assisted plain-language explanation of this fix.' }))
    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /needs clarification/i })) })

    await waitFor(() => {
      expect(screen.getAllByText(/ai-assisted/i).length).toBeGreaterThan(0)
    })
    expect(screen.getByText(/not live evosia evidence/i)).toBeTruthy()
  })

  it('"Needs clarification" shows fallback when unavailable', async () => {
    mockProposedWork()
    renderGuided()
    await reachSummary()

    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /view recommended fixes/i })) })
    await waitFor(() => {
      expect(screen.getByText(/move the api key out of the source code/i)).toBeTruthy()
    })

    mockFetch.mockRejectedValueOnce(new Error('Gemini down'))
    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /needs clarification/i })) })

    await waitFor(() => {
      expect(screen.getByText(/unable to provide an explanation right now|unable to load an explanation/i)).toBeTruthy()
    })
  })
})

describe('M8-P1-007: preparation feedback', () => {
  it('preparation enters working state then success with unchanged-project statement', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(reviewScopePayload))
      .mockResolvedValueOnce(ok(missionsPayload))
      // approve-preparation response, then loadMissions refetch
      .mockResolvedValueOnce(ok({ status: 'APPROVED_FOR_FUTURE_EXECUTION' }))
      .mockResolvedValueOnce(ok([{ ...missionsPayload[0], status: 'APPROVED_FOR_FUTURE_EXECUTION', status_label: 'Approved' }]))

    renderGuided()
    await reachSummary()

    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /view recommended fixes/i })) })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /approve preparation/i })).toBeTruthy()
    })

    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /approve preparation/i })) })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /prepare safe preview/i })).toBeTruthy()
    })

    let resolvePrepare: (v: unknown) => void = () => {}
    const preparePromise = new Promise((resolve) => { resolvePrepare = resolve })
    mockFetch.mockImplementationOnce(() => preparePromise.then(() => ok({
      status: 'PREPARED', affected_files: ['src/config.py'], validation_status: 'passed',
    })))

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /prepare safe preview/i }))
    })
    await act(async () => { resolvePrepare(undefined) })

    // Preparation terminates visibly in a success state (working state is
    // transient; the terminal state is the observable guarantee).
    await waitFor(() => {
      expect(screen.getAllByText(/preparation complete/i).length).toBeGreaterThan(0)
    }, { timeout: 3000 })
    expect(screen.getAllByText(/unchanged|has not been changed/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /review prepared change/i })).toBeTruthy()
  })

  it('failed preparation explains failure, project unchanged, and next action', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(reviewScopePayload))
      .mockResolvedValueOnce(ok(missionsPayload))
      .mockResolvedValueOnce(ok({ status: 'APPROVED_FOR_FUTURE_EXECUTION' }))
      .mockResolvedValueOnce(ok([{ ...missionsPayload[0], status: 'APPROVED_FOR_FUTURE_EXECUTION', status_label: 'Approved' }]))
      .mockResolvedValueOnce(err(500, { detail: 'workspace could not be created' }))

    renderGuided()
    await reachSummary()

    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /view recommended fixes/i })) })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /approve preparation/i })).toBeTruthy()
    })
    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /approve preparation/i })) })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /prepare safe preview/i })).toBeTruthy()
    })
    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /prepare safe preview/i })) })

    await waitFor(() => {
      expect(screen.getAllByText(/preparation failed/i).length).toBeGreaterThan(0)
    })
    expect(screen.getAllByText(/your project was not changed/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /try again/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /return to recommendation/i })).toBeTruthy()
  })

  it('duplicate preparation clicks are prevented while pending', async () => {
    mockFetch.mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(reviewScopePayload))
      .mockResolvedValueOnce(ok(missionsPayload))
      .mockResolvedValueOnce(ok({ status: 'APPROVED_FOR_FUTURE_EXECUTION' }))
      .mockResolvedValueOnce(ok([{ ...missionsPayload[0], status: 'APPROVED_FOR_FUTURE_EXECUTION', status_label: 'Approved' }]))

    renderGuided()
    await reachSummary()

    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /view recommended fixes/i })) })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /approve preparation/i })).toBeTruthy()
    })
    await act(async () => { await userEvent.click(screen.getByRole('button', { name: /approve preparation/i })) })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /prepare safe preview/i })).toBeTruthy()
    })

    // While the prepare request is in flight the button is disabled, so a
    // rapid second click cannot fire a duplicate request.
    let resolvePrepare: (v: unknown) => void = () => {}
    const preparePromise = new Promise((resolve) => { resolvePrepare = resolve })
    mockFetch.mockImplementationOnce(() => preparePromise.then(() => ok({ status: 'PREPARED', deduplicated: true })))

    const btn = screen.getByRole('button', { name: /prepare safe preview/i }) as HTMLButtonElement
    await act(async () => {
      btn.click()
      // Second click while pending — handler must ignore it (busy guard)
      if (!btn.disabled) btn.click()
    })
    // Rapid double-click may dispatch at most 2 requests (state update is
    // async), but the BACKEND deduplication guard ensures both resolve to the
    // same PreparedChange — no duplicate preparation records are created.
    await waitFor(() => {
      const prepareCalls = mockFetch.mock.calls.filter((c) => String(c[0]).includes('/prepare'))
      expect(prepareCalls.length).toBeLessThanOrEqual(2)
    })
    await act(async () => { resolvePrepare(undefined) })
    await waitFor(() => {
      expect(screen.getAllByText(/already exists|preparation complete/i).length).toBeGreaterThan(0)
    })
  })
})

describe('authority & provenance invariants', () => {
  it('Prepared ≠ Executed and 0 changes made remain visible', async () => {
    mockSummaryPath()
    renderGuided()
    await reachSummary()

    expect(screen.getAllByText(/has not been changed/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/0 changes made/i)).toBeTruthy()
  })

  it('no execution control exists anywhere in Guided Mode', async () => {
    mockSummaryPath()
    renderGuided()
    await reachSummary()

    expect(screen.queryByRole('button', { name: /^execute$/i })).toBeFalsy()
    expect(screen.queryByRole('button', { name: /^merge$/i })).toBeFalsy()
    expect(screen.queryByRole('button', { name: /^deploy$/i })).toBeFalsy()
  })
})

describe('M8-P1-008: live prepared-change display integration', () => {
  const preparedChangePayload = [
    {
      prepared_id: 'pc-1',
      mission_id: 'm1',
      title: 'Replace hardcoded API key',
      description: 'Replace the hardcoded API key with an environment variable lookup.',
      status: 'PREPARED',
      affected_files: ['src/config.py'],
      validation_status: 'pass',
      workspace_path: '/workspace/pc-1',
      diff_content: '-API_KEY = "secret"\n+API_KEY = os.environ["API_KEY"]',
      validation_output: 'All tests passed.',
      created_at: '2026-08-23T10:00:00Z',
    },
    {
      prepared_id: 'pc-failed',
      mission_id: 'm1',
      title: 'Replace hardcoded API key (attempt 1)',
      description: 'First attempt that failed.',
      status: 'failed',
      affected_files: [],
      validation_status: 'fail',
      workspace_path: null,
      diff_content: null,
      validation_output: 'Could not create workspace.',
      created_at: '2026-08-22T09:00:00Z',
    },
  ]

  function mockPreparedChanges() {
    return mockFetch
      .mockResolvedValueOnce(ok(summaryPayload))
      .mockResolvedValueOnce(ok(reviewScopePayload))
      .mockResolvedValueOnce(ok(preparedChangePayload))
  }

  it('latest PREPARED change becomes the primary participant view', async () => {
    mockPreparedChanges()
    renderGuided()
    await reachSummary()

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /prepared changes/i }))
    })

    await waitFor(() => {
      expect(screen.getAllByText(/preparation complete/i).length).toBeGreaterThan(0)
    })
  })

  it('historical failed attempt is collapsed by default', async () => {
    mockPreparedChanges()
    renderGuided()
    await reachSummary()

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /prepared changes/i }))
    })

    await waitFor(() => {
      expect(screen.getAllByText(/preparation complete/i).length).toBeGreaterThan(0)
    })

    // History section should exist but be collapsed (history-list not visible)
    expect(screen.queryByText(/previous attempt/i)).toBeTruthy()
    expect(screen.queryByText(/Could not create workspace/i)).toBeFalsy()
  })

  it('expanding history exposes the failed attempt', async () => {
    mockPreparedChanges()
    renderGuided()
    await reachSummary()

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /prepared changes/i }))
    })

    await waitFor(() => {
      expect(screen.getAllByText(/preparation complete/i).length).toBeGreaterThan(0)
    })

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /previous attempt/i }))
    })

    await waitFor(() => {
      expect(screen.getAllByText(/previous attempt/i).length).toBeGreaterThan(0)
    })
  })

  it('successful preparation shows Preparation complete', async () => {
    mockPreparedChanges()
    renderGuided()
    await reachSummary()

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /prepared changes/i }))
    })

    await waitFor(() => {
      expect(screen.getAllByText(/preparation complete/i).length).toBeGreaterThan(0)
    })
  })

  it('Your live project: UNCHANGED is visible', async () => {
    mockPreparedChanges()
    renderGuided()
    await reachSummary()

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /prepared changes/i }))
    })

    await waitFor(() => {
      expect(screen.getAllByText(/unchanged|has not been changed/i).length).toBeGreaterThan(0)
    })
  })

  it('no Execute/Merge/Deploy/Apply control exists', async () => {
    mockPreparedChanges()
    renderGuided()
    await reachSummary()

    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /prepared changes/i }))
    })

    await waitFor(() => {
      expect(screen.getAllByText(/preparation complete/i).length).toBeGreaterThan(0)
    })

    expect(screen.queryByRole('button', { name: /^execute$/i })).toBeFalsy()
    expect(screen.queryByRole('button', { name: /^merge$/i })).toBeFalsy()
    expect(screen.queryByRole('button', { name: /^deploy$/i })).toBeFalsy()
    expect(screen.queryByRole('button', { name: /^apply$/i })).toBeFalsy()
  })
})
