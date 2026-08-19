import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import LoginPage from '../pages/LoginPage'
import DashboardPage from '../pages/DashboardPage'
import RepositoriesPage from '../pages/RepositoriesPage'
import FindingsPage from '../pages/FindingsPage'
import ScansPage from '../pages/ScansPage'
import { AuthContext } from '../App'
import type { User } from '../lib/types'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

function ok(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body), status: 200, headers: new Headers() } as Response
}
function err(status: number, body: unknown) {
  return { ok: false, json: () => Promise.resolve(body), status, headers: new Headers() } as Response
}

const authUser: User = { id: 'u1', name: 'Test User', email: 'test@example.com', is_active: true, is_admin: false }

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

function pwInput() {
  return document.querySelector('input[type="password"]') as HTMLInputElement
}

function renderWithAuth(Page: React.ComponentType, entry = '/') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthContext.Provider value={{ user: authUser, login: vi.fn(), logout: vi.fn() }}>
        <Page />
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

describe('Login page', () => {
  it('renders form with email and password fields', async () => {
    mockFetch.mockImplementation(() => Promise.resolve(err(401, { detail: 'Not authenticated' })))
    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthContext.Provider value={{ user: null, login: vi.fn(), logout: vi.fn() }}>
          <LoginPage />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    expect(screen.getByText('EVOSIA Enterprise')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(pwInput()).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('calls login with email and password', async () => {
    const u = await userEvent.setup()
    const loginFn = vi.fn().mockResolvedValue(undefined)
    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthContext.Provider value={{ user: null, login: loginFn, logout: vi.fn() }}>
          <LoginPage />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    await u.type(screen.getByRole('textbox'), 'a@b.com')
    await u.type(pwInput(), 'pass')
    await u.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => {
      expect(loginFn).toHaveBeenCalledWith('a@b.com', 'pass')
    })
  })

  it('shows error on login failure', async () => {
    const u = await userEvent.setup()
    const loginFn = vi.fn().mockRejectedValue(new Error('Invalid credentials'))
    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthContext.Provider value={{ user: null, login: loginFn, logout: vi.fn() }}>
          <LoginPage />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    await u.type(screen.getByRole('textbox'), 'a@b.com')
    await u.type(pwInput(), 'wrong')
    await u.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Invalid credentials')).toBeInTheDocument()
  })
})

describe('Dashboard page', () => {
  it('shows stat cards with values', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/dashboard/activity-v2') return Promise.resolve(ok({
        repositories_total: 12, repositories_ready: 10, repositories_blocked: 2,
        scans_queued: 3, scans_running: 1, scans_completed_since: 8, scans_failed_since: 1,
        new_findings_since: 5, governance_approved_since: 2, governance_rejected_since: 0,
        draft_missions_since: 1, ci_failures_since: 0, latest_activity: [], average_repository_health: 78,
      }))
      if (url === '/api/dashboard/overnight') return Promise.resolve(ok({
        window_start: '2025-01-15T00:00:00Z', window_end: '2025-01-15T08:00:00Z',
        repositories_scanned: 10, blocked_repositories: 2, successful_scans: 8,
        failed_scans: 1, new_findings: 5, resolved_findings: 1, governance_decisions: 2,
        draft_missions: 1, ci_failures: 0, top_repositories_requiring_attention: [], summary: '8 of 10 scans succeeded',
      }))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(DashboardPage)
    await waitFor(() => {
      expect(screen.getByText('12')).toBeInTheDocument()
    })
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('78')).toBeInTheDocument()
    expect(screen.getByText(/8 of 10 scans succeeded/)).toBeInTheDocument()
  })

  it('shows loading then content', async () => {
    mockFetch.mockImplementation(() => new Promise(() => {}))
    renderWithAuth(DashboardPage)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })
})

describe('Repositories page', () => {
  it('lists repos with scan buttons', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/repositories') return Promise.resolve(ok([
        { id: 'r1', name: 'acme/web', url: '', default_branch: 'main', language: 'TS', status: 'active', provider: 'github', identifier: 'acme/web', commit_sha: 'abc1234', visibility: 'private', last_scanned_at: '2025-01-15T10:00:00Z', last_synced_at: '2025-01-15T10:00:00Z', health_score: 85, findings_count: 3, created_at: '2025-01-01', updated_at: '2025-01-15' },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(RepositoriesPage)
    await waitFor(() => {
      expect(screen.getByText('acme/web')).toBeInTheDocument()
    })
    expect(screen.getByText('85')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Scan' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sync' })).toBeInTheDocument()
  })

  it('shows empty state', async () => {
    mockFetch.mockImplementation(() => Promise.resolve(ok([])))
    renderWithAuth(RepositoriesPage)
    await waitFor(() => {
      expect(screen.getByText('No repositories registered yet')).toBeInTheDocument()
    })
  })
})

describe('Findings page', () => {
  it('renders findings table', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.startsWith('/api/findings')) return Promise.resolve(ok([
        { id: 'f1', severity: 'critical', title: 'Hardcoded secret', category: 'security', module: 'config.ts', status: 'open', created_at: '2025-01-15T10:00:00Z', finding_type: 'secret', description: '', repository_id: 'r1', priority_score: 90, effort: 'low' },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(FindingsPage)
    await waitFor(() => {
      expect(screen.getByText('Hardcoded secret')).toBeInTheDocument()
    })
    expect(screen.getByText('critical')).toBeInTheDocument()
    expect(screen.getByText('security')).toBeInTheDocument()
  })

  it('shows empty state', async () => {
    mockFetch.mockImplementation(() => Promise.resolve(ok([])))
    renderWithAuth(FindingsPage)
    await waitFor(() => {
      expect(screen.getByText('No findings')).toBeInTheDocument()
    })
  })

  it('filters by severity', async () => {
    const u = await userEvent.setup()
    const urls: string[] = []
    mockFetch.mockImplementation((url: string) => {
      urls.push(url)
      if (url.startsWith('/api/findings')) return Promise.resolve(ok([
        { id: 'f1', severity: 'critical', title: 'X', category: 's', module: null, status: 'open', created_at: '2025-01-15T10:00:00Z', finding_type: 't', description: '', repository_id: 'r1', priority_score: 90, effort: 'low' },
      ]))
      return Promise.resolve(ok({}))
    })
    renderWithAuth(FindingsPage)
    await screen.findByText('X')
    const select = screen.getByDisplayValue('All severities')
    await u.selectOptions(select, 'critical')
    await waitFor(() => {
      expect(urls.some(u => u.includes('severity=critical'))).toBe(true)
    })
  })
})

describe('Scans page', () => {
  it('shows cancel for running and retry for failed scans', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.startsWith('/api/scans') && !url.includes('cancel') && !url.includes('retry')) {
        return Promise.resolve(ok([
          { id: 's1', repository_id: 'r1', status: 'running', scan_type: 'full', branch: 'main', commit_sha: null, started_at: '2025-01-15T10:00:00Z', completed_at: null, duration_seconds: null, error_message: null, stages_completed: [], current_stage: 'metadata', findings_count: 0, attempt: 1, previous_scan_id: null, requested_by: null, cancellation_requested_at: null, cancelled_at: null, failure_classification: null, stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
          { id: 's2', repository_id: 'r1', status: 'failed', scan_type: 'full', branch: 'main', commit_sha: null, started_at: '2025-01-15T10:00:00Z', completed_at: '2025-01-15T10:01:00Z', duration_seconds: 60, error_message: 'timeout', stages_completed: ['metadata'], current_stage: null, findings_count: 0, attempt: 2, previous_scan_id: null, requested_by: null, cancellation_requested_at: null, cancelled_at: null, failure_classification: 'timeout', stage_timings: {}, created_at: '2025-01-15T10:00:00Z' },
        ]))
      }
      return Promise.resolve(ok({}))
    })
    renderWithAuth(ScansPage)
    await waitFor(() => {
      expect(screen.getByText('running')).toBeInTheDocument()
    })
    expect(screen.getByText('failed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('shows empty state', async () => {
    mockFetch.mockImplementation(() => Promise.resolve(ok([])))
    renderWithAuth(ScansPage)
    await waitFor(() => {
      expect(screen.getByText('No scan jobs')).toBeInTheDocument()
    })
  })

  it('filters by status', async () => {
    const u = await userEvent.setup()
    const urls: string[] = []
    mockFetch.mockImplementation((url: string) => {
      urls.push(url)
      if (url.startsWith('/api/scans') && !url.includes('cancel') && !url.includes('retry')) {
        return Promise.resolve(ok([]))
      }
      return Promise.resolve(ok({}))
    })
    renderWithAuth(ScansPage)
    await screen.findByText('No scan jobs')
    const select = screen.getByDisplayValue('All statuses')
    await u.selectOptions(select, 'running')
    await waitFor(() => {
      expect(urls.some(u => u.includes('status=running'))).toBe(true)
    })
  })
})
