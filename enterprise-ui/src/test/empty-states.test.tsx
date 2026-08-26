import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import MissionsPage from '../pages/MissionsPage'
import ReportsPage from '../pages/ReportsPage'
import { AuthContext } from '../App'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

function ok(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body), status: 200, headers: new Headers() } as Response
}

function renderWithAuth(component: React.ReactNode) {
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={{ user: { id: 'u1', name: 'Test User', email: 'test@example.com', is_active: true, is_admin: false }, login: vi.fn(), logout: vi.fn() }}>
        {component}
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

describe('P1-F02: MissionsPage empty state', () => {
  it('explains what Missions are when empty', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderWithAuth(<MissionsPage />)

    await waitFor(() => {
      expect(screen.getByText(/no missions yet/i)).toBeTruthy()
    })
    expect(screen.getByText(/missions will appear here when work progresses/i)).toBeTruthy()
  })

  it('contains a clearly labelled example', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderWithAuth(<MissionsPage />)

    await waitFor(() => {
      expect(screen.getByTestId('example-mission')).toBeTruthy()
    })
    expect(screen.getByText(/example mission/i)).toBeTruthy()
    expect(screen.getByText(/replace hardcoded api key with environment configuration/i)).toBeTruthy()
  })

  it('example cannot be mistaken for LIVE_EVOSIA_EVIDENCE', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderWithAuth(<MissionsPage />)

    await waitFor(() => {
      expect(screen.getByText(/example only — not a live evosia mission/i)).toBeTruthy()
    })
  })

  it('real missions render normally', async () => {
    const missions = [
      {
        id: 'm1',
        mission_id: 'MISSION-001',
        repository_id: 'repo-1',
        title: 'Real mission',
        description: 'A real mission',
        mission_type: 'remediation',
        status: 'pending',
        priority: 1,
        created_at: '2026-08-23T10:00:00Z',
      },
    ]
    mockFetch.mockResolvedValueOnce(ok(missions))
    renderWithAuth(<MissionsPage />)

    await waitFor(() => {
      expect(screen.getByText('Real mission')).toBeTruthy()
    })
    expect(screen.queryByTestId('example-mission')).toBeFalsy()
  })
})

describe('P1-F02: ReportsPage empty state', () => {
  it('explains what Reports are when empty', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderWithAuth(<ReportsPage />)

    await waitFor(() => {
      expect(screen.getByText(/no reports yet/i)).toBeTruthy()
    })
    expect(screen.getByText(/reports provide a record of evosia's reviews/i)).toBeTruthy()
  })

  it('contains a clearly labelled example', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderWithAuth(<ReportsPage />)

    await waitFor(() => {
      expect(screen.getByTestId('example-report')).toBeTruthy()
    })
    expect(screen.getByText(/example report/i)).toBeTruthy()
    expect(screen.getByText(/project review summary/i)).toBeTruthy()
  })

  it('example cannot be mistaken for LIVE_EVOSIA_EVIDENCE', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderWithAuth(<ReportsPage />)

    await waitFor(() => {
      expect(screen.getByText(/example only — not live evosia evidence/i)).toBeTruthy()
    })
  })

  it('real reports render normally', async () => {
    const reports = [
      {
        id: 'r1',
        mission_id: 'm1',
        repository_id: 'repo-1',
        title: 'Real report',
        status: 'COMPLETED',
        summary: 'A real report',
        report_data: {},
        duration_seconds: 10,
        tasks_planned: 5,
        tasks_completed: 5,
        tasks_failed: 0,
        created_at: '2026-08-23T10:00:00Z',
      },
    ]
    mockFetch.mockResolvedValueOnce(ok(reports))
    renderWithAuth(<ReportsPage />)

    await waitFor(() => {
      expect(screen.getByText('Real report')).toBeTruthy()
    })
    expect(screen.queryByTestId('example-report')).toBeFalsy()
  })
})
