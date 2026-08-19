import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DashboardPage from '../pages/DashboardPage'
import RepositoriesPage from '../pages/RepositoriesPage'
import RepositoryDetailPage from '../pages/RepositoryDetailPage'
import ScansPage from '../pages/ScansPage'
import FindingsPage from '../pages/FindingsPage'
import JournalPage from '../pages/JournalPage'
import LoginPage from '../pages/LoginPage'
import { AuthContext } from '../App'
import type { User } from '../lib/types'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

function ok(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body), status: 200, headers: new Headers() } as Response
}
function err(status: number, body: unknown) {
  return { ok: false, json: () => Promise.resolve(body), status, statusText: '', headers: new Headers() } as Response
}

const authUser: User = { id: 'u1', name: 'Test User', email: 'test@example.com', is_active: true, is_admin: false }

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

function renderWithAuth(Page: React.ComponentType, entry = '/', overrides: Partial<{ user: User | null }> = {}) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthContext.Provider value={{ user: overrides.user ?? authUser, login: vi.fn(), logout: vi.fn() }}>
        <Page />
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

// ─── Dashboard: Overnight Summary ───
describe('Dashboard: Overnight Summary', () => {
  it('renders overnight summary section with metrics', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/dashboard/activity-v2') return Promise.resolve(ok({
        repositories_total: 5, repositories_ready: 4, repositories_blocked: 1,
        scans_queued: 0, scans_running: 0, scans_completed_since: 3, scans_failed_since: 0,
        new_findings_since: 1, governance_approved_since: 0, governance_rejected_since: 0,
        draft_missions_since: 0, ci_failures_since: 0, latest_activity: [], average_repository_health: 82,
      }))
      if (url === '/api/dashboard/overnight') return Promise.resolve(ok({
        window_start: '2025-01-15T00:00:00Z', window_end: '2025-01-15T08:00:00Z',
        repositories_scanned: 5, blocked_repositories: 1, successful_scans: 3,
        failed_scans: 1, new_findings: 2, resolved_findings: 0, governance_decisions: 1,
        draft_missions: 0, ci_failures: 0, top_repositories_requiring_attention: [],
        summary: '3 of 5 scans succeeded overnight',
      }))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(DashboardPage)
    await waitFor(() => {
      expect(screen.getByText('5 repos scanned')).toBeInTheDocument()
    })
    expect(screen.getByText('3 successful')).toBeInTheDocument()
    expect(screen.getByText(/1 failed/)).toBeInTheDocument()
    expect(screen.getByText('2 new findings')).toBeInTheDocument()
    expect(screen.getByText('3 of 5 scans succeeded overnight')).toBeInTheDocument()
  })

  it('renders recent activity list', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/dashboard/activity-v2') return Promise.resolve(ok({
        repositories_total: 1, repositories_ready: 1, repositories_blocked: 0,
        scans_queued: 0, scans_running: 0, scans_completed_since: 1, scans_failed_since: 0,
        new_findings_since: 0, governance_approved_since: 0, governance_rejected_since: 0,
        draft_missions_since: 0, ci_failures_since: 0, average_repository_health: 95,
        latest_activity: [
          { id: 'ev1', event_id: 'e1', timestamp: '2025-01-15T10:00:00Z', event_type: 'scan.completed', stage: 'scan', repository_id: 'r1', actor: 'user1', payload: {}, payload_sha256: 'abc', created_at: '2025-01-15T10:00:00Z' },
          { id: 'ev2', event_id: 'e2', timestamp: '2025-01-15T10:05:00Z', event_type: 'finding.detected', stage: 'scan', repository_id: 'r1', actor: 'system', payload: {}, payload_sha256: 'def', created_at: '2025-01-15T10:05:00Z' },
        ],
      }))
      if (url === '/api/dashboard/overnight') return Promise.resolve(ok({
        window_start: '2025-01-15T00:00:00Z', window_end: '2025-01-15T08:00:00Z',
        repositories_scanned: 1, blocked_repositories: 0, successful_scans: 1,
        failed_scans: 0, new_findings: 0, resolved_findings: 0, governance_decisions: 0,
        draft_missions: 0, ci_failures: 0, top_repositories_requiring_attention: [], summary: '',
      }))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(DashboardPage)
    await waitFor(() => {
      expect(screen.getByText('scan.completed')).toBeInTheDocument()
    })
    expect(screen.getByText('finding.detected')).toBeInTheDocument()
    expect(screen.getByText('user1')).toBeInTheDocument()
    expect(screen.getByText('system')).toBeInTheDocument()
  })

  it('shows "No recent activity" when activity list is empty', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/dashboard/activity-v2') return Promise.resolve(ok({
        repositories_total: 0, repositories_ready: 0, repositories_blocked: 0,
        scans_queued: 0, scans_running: 0, scans_completed_since: 0, scans_failed_since: 0,
        new_findings_since: 0, governance_approved_since: 0, governance_rejected_since: 0,
        draft_missions_since: 0, ci_failures_since: 0, latest_activity: [], average_repository_health: null,
      }))
      if (url === '/api/dashboard/overnight') return Promise.resolve(ok({
        window_start: '2025-01-15T00:00:00Z', window_end: '2025-01-15T08:00:00Z',
        repositories_scanned: 0, blocked_repositories: 0, successful_scans: 0,
        failed_scans: 0, new_findings: 0, resolved_findings: 0, governance_decisions: 0,
        draft_missions: 0, ci_failures: 0, top_repositories_requiring_attention: [], summary: '',
      }))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(DashboardPage)
    await waitFor(() => {
      expect(screen.getByText('No recent activity')).toBeInTheDocument()
    })
  })

  it('shows "Failed to load dashboard" on API error', async () => {
    mockFetch.mockImplementation(() => Promise.resolve(err(500, { detail: 'Server error' })))
    renderWithAuth(DashboardPage)
    await waitFor(() => {
      expect(screen.getByText('Failed to load dashboard')).toBeInTheDocument()
    })
  })
})

// ─── Repositories: Card Details ───
describe('Repositories: Card Details', () => {
  it('renders repository card with all metadata', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/repositories') return Promise.resolve(ok([
        {
          id: 'r1', name: 'acme/web', url: 'https://github.com/acme/web', default_branch: 'main',
          language: 'TypeScript', status: 'active', provider: 'github', identifier: 'acme/web',
          commit_sha: 'abc1234def5678', visibility: 'private', last_scanned_at: '2025-01-15T10:00:00Z',
          last_synced_at: '2025-01-15T09:30:00Z', health_score: 85, findings_count: 3,
          created_at: '2025-01-01', updated_at: '2025-01-15',
        },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(RepositoriesPage)
    await waitFor(() => {
      expect(screen.getByText('acme/web')).toBeInTheDocument()
    })
    expect(screen.getByText('TypeScript')).toBeInTheDocument()
    expect(screen.getByText('85')).toBeInTheDocument()
    expect(screen.getByText('private')).toBeInTheDocument()
    expect(screen.getByText('github')).toBeInTheDocument()
  })

  it('renders multiple repository cards', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/repositories') return Promise.resolve(ok([
        { id: 'r1', name: 'acme/web', url: '', default_branch: 'main', language: 'TS', status: 'active', provider: 'github', identifier: 'acme/web', commit_sha: 'abc1234', visibility: 'private', last_scanned_at: null, last_synced_at: null, health_score: 90, findings_count: 0, created_at: '2025-01-01', updated_at: '2025-01-15' },
        { id: 'r2', name: 'acme/api', url: '', default_branch: 'main', language: 'Python', status: 'active', provider: 'github', identifier: 'acme/api', commit_sha: 'def5678', visibility: 'public', last_scanned_at: '2025-01-15T10:00:00Z', last_synced_at: '2025-01-15T10:00:00Z', health_score: 72, findings_count: 5, created_at: '2025-01-01', updated_at: '2025-01-15' },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(RepositoriesPage)
    await waitFor(() => {
      expect(screen.getByText('acme/web')).toBeInTheDocument()
    })
    expect(screen.getByText('acme/api')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('public')).toBeInTheDocument()
  })
})

// ─── Repository Detail: Overview Tab ───
function renderRepoDetail(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthContext.Provider value={{ user: authUser, login: vi.fn(), logout: vi.fn() }}>
        <Routes>
          <Route path="/repositories/:repoId" element={<RepositoryDetailPage />} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

describe('Repository Detail: Overview Tab', () => {
  it('renders overview tab with repository metadata', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/repositories/r1') return Promise.resolve(ok({
        id: 'r1', name: 'acme/web', url: 'https://github.com/acme/web', default_branch: 'main',
        language: 'TypeScript', status: 'active', provider: 'github', identifier: 'acme/web',
        commit_sha: 'abc1234def5678', visibility: 'private', last_scanned_at: '2025-01-15T10:00:00Z',
        last_synced_at: '2025-01-15T09:30:00Z', health_score: 85, findings_count: 3,
        created_at: '2025-01-01', updated_at: '2025-01-15',
      }))
      if (url.startsWith('/api/scans')) return Promise.resolve(ok([]))
      return Promise.resolve(ok({}))
    })
    renderRepoDetail('/repositories/r1')
    await waitFor(() => {
      expect(screen.getByText('acme/web')).toBeInTheDocument()
    })
    expect(screen.getByText('github')).toBeInTheDocument()
    expect(screen.getByText('private')).toBeInTheDocument()
    expect(screen.getByText('main')).toBeInTheDocument()
    expect(screen.getByText('85')).toBeInTheDocument()
  })
})

// ─── Repository Detail: Scan Timeline ───
describe('Repository Detail: Scan Timeline', () => {
  it('renders scan timeline with stage progression', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/repositories/r1') return Promise.resolve(ok({
        id: 'r1', name: 'acme/web', url: '', default_branch: 'main', language: 'TS', status: 'active', provider: 'github', identifier: 'acme/web', commit_sha: 'abc', visibility: 'private', last_scanned_at: null, last_synced_at: null, health_score: 85, findings_count: 0, created_at: '2025-01-01', updated_at: '2025-01-15',
      }))
      if (url.startsWith('/api/scans')) return Promise.resolve(ok([
        {
          id: 's1', repository_id: 'r1', status: 'completed', scan_type: 'full', branch: 'main',
          commit_sha: 'abc1234', started_at: '2025-01-15T10:00:00Z', completed_at: '2025-01-15T10:05:00Z',
          duration_seconds: 300, error_message: null, stages_completed: ['metadata', 'repository_analysis', 'engineering_analysis', 'governance_analysis', 'journal_sync', 'finding_generation'],
          current_stage: null, findings_count: 3, attempt: 1, previous_scan_id: null, requested_by: 'user1',
          cancellation_requested_at: null, cancelled_at: null, failure_classification: null,
          stage_timings: {
            metadata: { started_at: '2025-01-15T10:00:00Z', completed_at: '2025-01-15T10:00:30Z', duration_seconds: 30 },
            repository_analysis: { started_at: '2025-01-15T10:00:30Z', completed_at: '2025-01-15T10:01:30Z', duration_seconds: 60 },
            engineering_analysis: { started_at: '2025-01-15T10:01:30Z', completed_at: '2025-01-15T10:03:00Z', duration_seconds: 90 },
            governance_analysis: { started_at: '2025-01-15T10:03:00Z', completed_at: '2025-01-15T10:03:30Z', duration_seconds: 30 },
            journal_sync: { started_at: '2025-01-15T10:03:30Z', completed_at: '2025-01-15T10:04:00Z', duration_seconds: 30 },
            finding_generation: { started_at: '2025-01-15T10:04:00Z', completed_at: '2025-01-15T10:05:00Z', duration_seconds: 60 },
          },
          created_at: '2025-01-15T10:00:00Z',
        },
      ]))
      return Promise.resolve(ok({}))
    })
    renderRepoDetail('/repositories/r1')
    // Click Scans tab
    await waitFor(() => {
      expect(screen.getByText('acme/web')).toBeInTheDocument()
    })
    const u = await userEvent.setup()
    // Click the Scans tab button
    const tabsContainer = document.querySelector('.tabs')
    if (tabsContainer) {
      const scansBtn = Array.from(tabsContainer.querySelectorAll('button')).find(b => b.textContent === 'Scans')
      if (scansBtn) await u.click(scansBtn)
    }
    // Click on the scan row to select it and show timeline
    await waitFor(() => {
      expect(screen.getByText('completed')).toBeInTheDocument()
    })
    const scanRow = screen.getByText('s1')
    await u.click(scanRow.closest('tr')!)
    await waitFor(() => {
      expect(screen.getByText('Scan Timeline')).toBeInTheDocument()
    })
    expect(screen.getByText(/metadata/)).toBeInTheDocument()
    expect(screen.getByText(/materialization/)).toBeInTheDocument()
    expect(screen.getByText(/readiness/)).toBeInTheDocument()
    expect(screen.getByText(/repository intelligence/)).toBeInTheDocument()
    expect(screen.getByText(/engineering intelligence/)).toBeInTheDocument()
    expect(screen.getByText(/governance/)).toBeInTheDocument()
    expect(screen.getByText(/mission recommendation/)).toBeInTheDocument()
    expect(screen.getByText(/persistence/)).toBeInTheDocument()
    expect(screen.getByText(/journal/)).toBeInTheDocument()
  })

  it('shows error message for failed scans', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/repositories/r1') return Promise.resolve(ok({
        id: 'r1', name: 'acme/web', url: '', default_branch: 'main', language: 'TS', status: 'active', provider: 'github', identifier: 'acme/web', commit_sha: 'abc', visibility: 'private', last_scanned_at: null, last_synced_at: null, health_score: 85, findings_count: 0, created_at: '2025-01-01', updated_at: '2025-01-15',
      }))
      if (url.startsWith('/api/scans')) return Promise.resolve(ok([
        {
          id: 's2', repository_id: 'r1', status: 'failed', scan_type: 'full', branch: 'main',
          commit_sha: null, started_at: '2025-01-15T10:00:00Z', completed_at: '2025-01-15T10:01:00Z',
          duration_seconds: 60, error_message: 'GitHub API rate limit exceeded', stages_completed: ['metadata'],
          current_stage: null, findings_count: 0, attempt: 1, previous_scan_id: null, requested_by: null,
          cancellation_requested_at: null, cancelled_at: null, failure_classification: 'rate_limit',
          stage_timings: {}, created_at: '2025-01-15T10:00:00Z',
        },
      ]))
      return Promise.resolve(ok({}))
    })
    renderRepoDetail('/repositories/r1')
    await waitFor(() => {
      expect(screen.getByText('acme/web')).toBeInTheDocument()
    })
    const u = await userEvent.setup()
    const tabsContainer = document.querySelector('.tabs')
    if (tabsContainer) {
      const scansBtn = Array.from(tabsContainer.querySelectorAll('button')).find(b => b.textContent === 'Scans')
      if (scansBtn) await u.click(scansBtn)
    }
    // Click on the scan row to select it
    await waitFor(() => {
      expect(screen.getByText('failed')).toBeInTheDocument()
    })
    const scanRow = screen.getByText('s2')
    await u.click(scanRow.closest('tr')!)
    await waitFor(() => {
      expect(screen.getByText('GitHub API rate limit exceeded')).toBeInTheDocument()
    })
  })
})

// ─── Scans Page: State Rendering ───
describe('Scans Page: State Rendering', () => {
  it('renders different status badges correctly', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.startsWith('/api/scans')) return Promise.resolve(ok([
        { id: 's1', repository_id: 'r1', status: 'pending', scan_type: 'full', branch: 'main', commit_sha: null, started_at: null, completed_at: null, duration_seconds: null, error_message: null, stages_completed: [], current_stage: null, findings_count: 0, attempt: 1, previous_scan_id: null, requested_by: null, cancellation_requested_at: null, cancelled_at: null, failure_classification: null, stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
        { id: 's2', repository_id: 'r1', status: 'running', scan_type: 'full', branch: 'main', commit_sha: null, started_at: '2025-01-15T10:00:00Z', completed_at: null, duration_seconds: null, error_message: null, stages_completed: ['metadata'], current_stage: 'repository_analysis', findings_count: 0, attempt: 1, previous_scan_id: null, requested_by: null, cancellation_requested_at: null, cancelled_at: null, failure_classification: null, stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
        { id: 's3', repository_id: 'r1', status: 'completed', scan_type: 'full', branch: 'main', commit_sha: 'abc', started_at: '2025-01-15T10:00:00Z', completed_at: '2025-01-15T10:05:00Z', duration_seconds: 300, error_message: null, stages_completed: ['metadata', 'repository_analysis', 'engineering_analysis', 'governance_analysis', 'journal_sync', 'finding_generation'], current_stage: null, findings_count: 3, attempt: 1, previous_scan_id: null, requested_by: null, cancellation_requested_at: null, cancelled_at: null, failure_classification: null, stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
        { id: 's4', repository_id: 'r1', status: 'cancelled', scan_type: 'full', branch: 'main', commit_sha: null, started_at: '2025-01-15T10:00:00Z', completed_at: '2025-01-15T10:00:30Z', duration_seconds: 30, error_message: 'Cancelled by user', stages_completed: ['metadata'], current_stage: null, findings_count: 0, attempt: 1, previous_scan_id: null, requested_by: 'admin', cancellation_requested_at: '2025-01-15T10:00:30Z', cancelled_at: '2025-01-15T10:00:30Z', failure_classification: null, stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(ScansPage)
    await waitFor(() => {
      expect(screen.getByText('pending')).toBeInTheDocument()
    })
    expect(screen.getByText('running')).toBeInTheDocument()
    expect(screen.getByText('completed')).toBeInTheDocument()
    expect(screen.getByText('cancelled')).toBeInTheDocument()
    expect(screen.getByText('repository_analysis')).toBeInTheDocument()
  })

  it('shows duration for completed scans', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.startsWith('/api/scans')) return Promise.resolve(ok([
        { id: 's1', repository_id: 'r1', status: 'completed', scan_type: 'full', branch: 'main', commit_sha: 'abc', started_at: '2025-01-15T10:00:00Z', completed_at: '2025-01-15T10:05:00Z', duration_seconds: 300, error_message: null, stages_completed: [], current_stage: null, findings_count: 0, attempt: 1, previous_scan_id: null, requested_by: null, cancellation_requested_at: null, cancelled_at: null, failure_classification: null, stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(ScansPage)
    await waitFor(() => {
      expect(screen.getByText('300.0s')).toBeInTheDocument()
    })
  })
})

// ─── Scans Page: Cancel Interaction ───
describe('Scans Page: Cancel Interaction', () => {
  it('calls cancel API and refreshes scan list', async () => {
    const u = await userEvent.setup()
    const urls: string[] = []
    mockFetch.mockImplementation((url: string, opts?: any) => {
      urls.push(url)
      if (url === '/api/scans/s1/cancel' && opts?.method === 'POST') {
        return Promise.resolve(ok({ id: 's1', status: 'cancelled' }))
      }
      if (url.startsWith('/api/scans') && !url.includes('cancel') && !url.includes('retry')) {
        return Promise.resolve(ok([
          { id: 's1', repository_id: 'r1', status: 'running', scan_type: 'full', branch: 'main', commit_sha: null, started_at: '2025-01-15T10:00:00Z', completed_at: null, duration_seconds: null, error_message: null, stages_completed: [], current_stage: 'metadata', findings_count: 0, attempt: 1, previous_scan_id: null, requested_by: null, cancellation_requested_at: null, cancelled_at: null, failure_classification: null, stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
        ]))
      }
      return Promise.resolve(ok({}))
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderWithAuth(ScansPage)
    await waitFor(() => {
      expect(screen.getByText('running')).toBeInTheDocument()
    })
    await u.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => {
      expect(urls).toContain('/api/scans/s1/cancel')
    })
  })
})

// ─── Scans Page: Retry Interaction ───
describe('Scans Page: Retry Interaction', () => {
  it('calls retry API and refreshes scan list', async () => {
    const u = await userEvent.setup()
    const urls: string[] = []
    mockFetch.mockImplementation((url: string, opts?: any) => {
      urls.push(url)
      if (url === '/api/scans/s1/retry' && opts?.method === 'POST') {
        return Promise.resolve(ok({ id: 's1', status: 'failed' }))
      }
      if (url.startsWith('/api/scans') && !url.includes('cancel') && !url.includes('retry')) {
        return Promise.resolve(ok([
          { id: 's1', repository_id: 'r1', status: 'failed', scan_type: 'full', branch: 'main', commit_sha: null, started_at: '2025-01-15T10:00:00Z', completed_at: '2025-01-15T10:01:00Z', duration_seconds: 60, error_message: 'timeout', stages_completed: [], current_stage: null, findings_count: 0, attempt: 1, previous_scan_id: null, requested_by: null, cancellation_requested_at: null, cancelled_at: null, failure_classification: 'timeout', stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
        ]))
      }
      return Promise.resolve(ok({}))
    })
    renderWithAuth(ScansPage)
    await waitFor(() => {
      expect(screen.getByText('failed')).toBeInTheDocument()
    })
    await u.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => {
      expect(urls).toContain('/api/scans/s1/retry')
    })
  })
})

// ─── Structured API Errors ───
describe('Structured API Errors', () => {
  it('shows error alert on cancel failure', async () => {
    const u = await userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.spyOn(window, 'alert').mockImplementation(() => {})
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url === '/api/scans/s1/cancel' && opts?.method === 'POST') {
        return Promise.resolve(err(400, { detail: 'Scan already completed' }))
      }
      if (url.startsWith('/api/scans')) return Promise.resolve(ok([
        { id: 's1', repository_id: 'r1', status: 'running', scan_type: 'full', branch: 'main', commit_sha: null, started_at: '2025-01-15T10:00:00Z', completed_at: null, duration_seconds: null, error_message: null, stages_completed: [], current_stage: 'metadata', findings_count: 0, attempt: 1, previous_scan_id: null, requested_by: null, cancellation_requested_at: null, cancelled_at: null, failure_classification: null, stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(ScansPage)
    await waitFor(() => {
      expect(screen.getByText('running')).toBeInTheDocument()
    })
    await u.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith('Scan already completed')
    })
  })

  it('shows error alert on retry failure', async () => {
    const u = await userEvent.setup()
    vi.spyOn(window, 'alert').mockImplementation(() => {})
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url === '/api/scans/s1/retry' && opts?.method === 'POST') {
        return Promise.resolve(err(400, { detail: 'Scan is still running' }))
      }
      if (url.startsWith('/api/scans')) return Promise.resolve(ok([
        { id: 's1', repository_id: 'r1', status: 'failed', scan_type: 'full', branch: 'main', commit_sha: null, started_at: '2025-01-15T10:00:00Z', completed_at: '2025-01-15T10:01:00Z', duration_seconds: 60, error_message: 'timeout', stages_completed: [], current_stage: null, findings_count: 0, attempt: 1, previous_scan_id: null, requested_by: null, cancellation_requested_at: null, cancelled_at: null, failure_classification: 'timeout', stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(ScansPage)
    await waitFor(() => {
      expect(screen.getByText('failed')).toBeInTheDocument()
    })
    await u.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith('Scan is still running')
    })
  })
})

// ─── Authentication Expiry ───
describe('Authentication Expiry', () => {
  it('shows login form when user is null (expired session)', () => {
    renderWithAuth(LoginPage, '/login', { user: null })
    expect(screen.getByText('EVOSIA Enterprise')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })
})

// ─── Findings: Empty and Filter States ───
describe('Findings: Empty and Filter States', () => {
  it('shows loading state', async () => {
    mockFetch.mockImplementation(() => new Promise(() => {}))
    renderWithAuth(FindingsPage)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders findings with severity badges', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.startsWith('/api/findings')) return Promise.resolve(ok([
        { id: 'f1', severity: 'critical', title: 'Hardcoded secret', category: 'security', module: 'config.ts', status: 'open', created_at: '2025-01-15T10:00:00Z', finding_type: 'secret', description: '', repository_id: 'r1', priority_score: 90, effort: 'low' },
        { id: 'f2', severity: 'medium', title: 'Outdated dependency', category: 'dependency', module: 'package.json', status: 'open', created_at: '2025-01-15T10:05:00Z', finding_type: 'dependency', description: '', repository_id: 'r1', priority_score: 50, effort: 'medium' },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(FindingsPage)
    await waitFor(() => {
      expect(screen.getByText('Hardcoded secret')).toBeInTheDocument()
    })
    expect(screen.getByText('Outdated dependency')).toBeInTheDocument()
    expect(screen.getByText('dependency')).toBeInTheDocument()
  })
})

// ─── Journal Page ───
describe('Journal Page', () => {
  it('renders journal events with type badges', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.startsWith('/api/journal')) return Promise.resolve(ok([
        { id: 'j1', event_id: 'e1', timestamp: '2025-01-15T10:00:00Z', event_type: 'readiness.assessed', stage: 'readiness', repository_id: 'r1', actor: 'user1', payload: {}, payload_sha256: 'abc', created_at: '2025-01-15T10:00:00Z' },
        { id: 'j2', event_id: 'e2', timestamp: '2025-01-15T10:05:00Z', event_type: 'mission.created', stage: 'mission', repository_id: 'r1', actor: 'system', payload: {}, payload_sha256: 'def', created_at: '2025-01-15T10:05:00Z' },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(JournalPage)
    await waitFor(() => {
      expect(screen.getByText('user1')).toBeInTheDocument()
    })
    expect(screen.getByText('system')).toBeInTheDocument()
  })

  it('shows empty state', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.startsWith('/api/journal')) return Promise.resolve(ok([]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(JournalPage)
    await waitFor(() => {
      expect(screen.getByText('No journal events')).toBeInTheDocument()
    })
  })

  it('filters by event type', async () => {
    const u = await userEvent.setup()
    const urls: string[] = []
    mockFetch.mockImplementation((url: string) => {
      urls.push(url)
      if (url.startsWith('/api/journal')) return Promise.resolve(ok([]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(JournalPage)
    await screen.findByText('No journal events')
    const select = screen.getByDisplayValue('All event types')
    await u.selectOptions(select, 'readiness.assessed')
    await waitFor(() => {
      expect(urls.some(u => u.includes('event_type=readiness.assessed'))).toBe(true)
    })
  })
})

// ─── Polling Refresh ───
describe('Polling Refresh', () => {
  it('Scans page re-fetches on status filter change', async () => {
    const u = await userEvent.setup()
    const urls: string[] = []
    mockFetch.mockImplementation((url: string) => {
      urls.push(url)
      if (url.startsWith('/api/scans')) return Promise.resolve(ok([]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(ScansPage)
    await screen.findByText('No scan jobs')
    const select = screen.getByDisplayValue('All statuses')
    await u.selectOptions(select, 'running')
    await waitFor(() => {
      expect(urls.filter(u => u.includes('status=running'))).toHaveLength(1)
    })
    await u.selectOptions(select, 'failed')
    await waitFor(() => {
      expect(urls.filter(u => u.includes('status=failed'))).toHaveLength(1)
    })
  })

  it('Journal page re-fetches on type filter change', async () => {
    const u = await userEvent.setup()
    const urls: string[] = []
    mockFetch.mockImplementation((url: string) => {
      urls.push(url)
      if (url.startsWith('/api/journal')) return Promise.resolve(ok([]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(JournalPage)
    await screen.findByText('No journal events')
    const select = screen.getByDisplayValue('All event types')
    await u.selectOptions(select, 'readiness.assessed')
    await waitFor(() => {
      expect(urls.filter(u => u.includes('event_type=readiness.assessed'))).toHaveLength(1)
    })
  })
})
