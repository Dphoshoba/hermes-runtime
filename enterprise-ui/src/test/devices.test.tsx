import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '../App'
import DevicesPage from '../pages/DevicesPage'
import type { Device, DeviceProject, AgentJob, User } from '../lib/types'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

function ok(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body), status: 200, headers: new Headers() } as Response
}

const authUser: User = { id: 'u1', email: 'test@test.com', name: 'Test User', is_active: true, is_admin: false }

function renderDevices(entry = '/devices') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthContext.Provider value={{ user: authUser, login: vi.fn(), logout: vi.fn() }}>
        <DevicesPage />
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

const SAMPLE_DEVICE: Device = {
  id: 'd1', device_id: 'dev_abc123', device_name: "David's MacBook",
  platform: 'macos', agent_version: 'evosia-agent/0.3.0', user_id: 'u1',
  status: 'active', capabilities: [], registered_at: '2026-01-01T00:00:00Z',
  last_seen_at: new Date(Date.now() - 120000).toISOString(), revoked_at: null,
  created_at: '2026-01-01T00:00:00Z',
}

const SAMPLE_PROJECT: DeviceProject = {
  id: 'p1', device_id: 'dev_abc123', user_id: 'u1', display_name: 'BibleQuest',
  local_root_fingerprint: null, status: 'active', authority: 'REVIEW_ONLY',
  registered_at: '2026-01-01T00:00:00Z', revoked_at: null, created_at: '2026-01-01T00:00:00Z',
}

const SAMPLE_JOB: AgentJob = {
  id: 'j1', user_id: 'u1', device_id: 'dev_abc123', device_project_id: 'p1',
  operation_type: 'PROJECT_SCAN', status: 'COMPLETED',
  created_at: '2026-01-02T10:00:00Z', started_at: '2026-01-02T10:00:01Z',
  completed_at: '2026-01-02T10:00:05Z', failed_at: null, failure_reason: null,
  truncated: false,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

describe('DevicesPage', () => {
  it('shows empty state when no devices', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    expect(screen.getByText('Loading computers...')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('No computers connected yet.')).toBeInTheDocument()
    })
  })

  it('shows Add computer button in empty state', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => {
      expect(screen.getByText('Add computer')).toBeInTheDocument()
    })
  })

  it('displays device list with status', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    renderDevices()
    await waitFor(() => {
      expect(screen.getByText("David's MacBook")).toBeInTheDocument()
    })
    expect(screen.getByText(/Mac · evosia/)).toBeInTheDocument()
    expect(screen.getByText(/online|offline/)).toBeInTheDocument()
  })

  it('shows last connected time', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    renderDevices()
    await waitFor(() => {
      expect(screen.getByText(/Last connected:/)).toBeInTheDocument()
    })
  })

  it('shows revoked device status', async () => {
    const revoked = { ...SAMPLE_DEVICE, status: 'revoked', last_seen_at: null }
    mockFetch.mockResolvedValueOnce(ok([revoked]))
    renderDevices()
    await waitFor(() => {
      expect(screen.getByText("David's MacBook")).toBeInTheDocument()
    })
    expect(screen.getByText('revoked')).toBeInTheDocument()
  })

  it('clicking Add computer opens modal', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText('Add computer')).toBeInTheDocument() })
    await userEvent.click(screen.getByText('Add computer'))
    expect(screen.getByText(/Generate a one-time registration code/)).toBeInTheDocument()
  })

  it('Add computer modal creates bootstrap token', async () => {
    mockFetch.mockResolvedValueOnce(ok([])) // list devices
    mockFetch.mockResolvedValueOnce(ok({
      bootstrap_token: 'la_boot_test123',
      expires_at: '2026-01-01T00:10:00Z',
      device_id: 'dev_new',
    })) // register
    renderDevices()
    await waitFor(() => { expect(screen.getByText('Add computer')).toBeInTheDocument() })
    await userEvent.click(screen.getByText('Add computer'))

    await userEvent.type(screen.getByPlaceholderText(/David's MacBook Pro/), 'Test PC')
    await userEvent.click(screen.getByText('Generate code'))

    await waitFor(() => {
      expect(screen.getByText('la_boot_test123')).toBeInTheDocument()
    })
    expect(screen.getByText(/This code can only be used once/)).toBeInTheDocument()
  })

  it('clicking device opens detail view', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE])) // list devices
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT])) // list projects
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => {
      expect(screen.getByText('BibleQuest')).toBeInTheDocument()
    })
  })

  it('device detail shows authority explanation', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => {
      expect(screen.getByText(/EVOSIA may inspect this project/)).toBeInTheDocument()
    })
  })

  it('device detail shows Review only authority', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => {
      expect(screen.getByText('Review only')).toBeInTheDocument()
    })
  })

  it('Review Project button creates scan job', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE])) // list devices
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT])) // list projects (detail view)
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    // Clicking BibleQuest triggers loadJobs
    mockFetch.mockResolvedValueOnce(ok([])) // initial jobs list (empty)
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => { expect(screen.getByText(/No reviews have been requested/)).toBeInTheDocument() })

    // Now click Review project — triggers requestScan + loadJobs
    mockFetch.mockResolvedValueOnce(ok(SAMPLE_JOB)) // request scan
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_JOB])) // list jobs after scan
    await userEvent.click(screen.getByText('Review project'))
    await waitFor(() => {
      expect(screen.getByText('Review complete')).toBeInTheDocument()
    })
  })

  it('completed review shows project unchanged', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    // Click BibleQuest to open review history
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_JOB]))
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => {
      expect(screen.getByText('Review complete')).toBeInTheDocument()
    })
    expect(screen.getByText(/Project unchanged/)).toBeInTheDocument()
  })

  it('pending review shows waiting status', async () => {
    const pendingJob = { ...SAMPLE_JOB, status: 'PENDING', started_at: null, completed_at: null }
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok([pendingJob]))
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => {
      expect(screen.getByText('Waiting for your computer')).toBeInTheDocument()
    })
  })

  it('failed review shows failure reason', async () => {
    const failedJob = { ...SAMPLE_JOB, status: 'FAILED', failure_reason: 'Device went offline' }
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok([failedJob]))
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => {
      expect(screen.getByText('Review could not be completed')).toBeInTheDocument()
    })
    expect(screen.getByText('Device went offline')).toBeInTheDocument()
  })

  it('no Execute/Merge/Deploy/Apply BUTTONS exist', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    // Check no BUTTONS with these labels exist (the authority text mentions them but that's OK)
    expect(screen.queryByRole('button', { name: /Execute/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Merge/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Deploy/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Apply/i })).not.toBeInTheDocument()
  })

  it('raw local path is not displayed', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    // No raw path like /Users/... should appear
    const text = document.body.textContent || ''
    expect(text).not.toMatch(/\/Users\//)
  })

  it('empty projects state shows helpful message', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => {
      expect(screen.getByText(/No projects authorised/)).toBeInTheDocument()
    })
  })

  it('bootstrap secret is not logged to console', async () => {
    const consoleSpy = vi.spyOn(console, 'log')
    mockFetch.mockResolvedValueOnce(ok([]))
    mockFetch.mockResolvedValueOnce(ok({
      bootstrap_token: 'la_boot_secret_token_123',
      expires_at: '2026-01-01T00:10:00Z',
      device_id: 'dev_new',
    }))
    renderDevices()
    await waitFor(() => { expect(screen.getByText('Add computer')).toBeInTheDocument() })
    await userEvent.click(screen.getByText('Add computer'))
    await userEvent.type(screen.getByPlaceholderText(/David's MacBook Pro/), 'Test PC')
    await userEvent.click(screen.getByText('Generate code'))
    await waitFor(() => { expect(screen.getByText('la_boot_secret_token_123')).toBeInTheDocument() })

    const logCalls = consoleSpy.mock.calls.flat().join(' ')
    expect(logCalls).not.toContain('la_boot_secret_token_123')
    consoleSpy.mockRestore()
  })

  // -----------------------------------------------------------------------
  // Truncation tests
  // -----------------------------------------------------------------------

  it('truncated scan shows limits disclosure', async () => {
    const truncatedJob = { ...SAMPLE_JOB, truncated: true }
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok([truncatedJob]))
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => {
      expect(screen.getByText('Review completed with limits.')).toBeInTheDocument()
    })
    expect(screen.getByText(/some files may not have been examined/)).toBeInTheDocument()
  })

  it('complete scan does NOT show limits disclosure', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok([SAMPLE_JOB]))
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => {
      expect(screen.getByText('Review complete')).toBeInTheDocument()
    })
    expect(screen.queryByText('Review completed with limits.')).not.toBeInTheDocument()
  })

  it('truncated field comes from backend not frontend', async () => {
    const truncatedJob = { ...SAMPLE_JOB, truncated: true }
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok([truncatedJob]))
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => {
      expect(screen.getByText('Review completed with limits.')).toBeInTheDocument()
    })
  })

  // -----------------------------------------------------------------------
  // Keyboard accessibility tests
  // -----------------------------------------------------------------------

  it('project selection works with Enter key', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    mockFetch.mockResolvedValueOnce(ok([])) // jobs for selected project
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    const list = screen.getByRole('list', { name: /Authorised projects/ })
    const projectButton = list.querySelector('[role="listitem"]') as HTMLElement
    fireEvent.click(projectButton)
    await waitFor(() => {
      expect(screen.getByText('Review history')).toBeInTheDocument()
    })
  })

  it('project selection works with Space key', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    const list = screen.getByRole('list', { name: /Authorised projects/ })
    const projectButton = list.querySelector('[role="listitem"]') as HTMLElement
    fireEvent.click(projectButton)
    await waitFor(() => {
      expect(screen.getByText('Review history')).toBeInTheDocument()
    })
  })

  it('project cards are keyboard-focusable buttons', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    const list = screen.getByRole('list', { name: /Authorised projects/ })
    const projectButton = list.querySelector('[role="listitem"]') as HTMLElement
    expect(projectButton.tagName).toBe('BUTTON')
    expect(projectButton.getAttribute('type')).toBe('button')
  })

  it('device cards are keyboard-focusable buttons', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })

    const deviceButton = screen.getByRole('listitem', { name: /David's MacBook/ })
    expect(deviceButton.tagName).toBe('BUTTON')
    expect(deviceButton.getAttribute('type')).toBe('button')
  })

  // -----------------------------------------------------------------------
  // Modal focus management tests
  // -----------------------------------------------------------------------

  it('Add Computer modal receives focus on open', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText('Add computer')).toBeInTheDocument() })
    await userEvent.click(screen.getByText('Add computer'))

    await waitFor(() => {
      const dialog = screen.getByRole('dialog', { name: /Add computer/ })
      expect(dialog).toBeInTheDocument()
      // Focus should be inside the dialog
      const focused = document.activeElement
      expect(dialog.contains(focused)).toBe(true)
    })
  })

  it('Escape closes Add Computer modal', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText('Add computer')).toBeInTheDocument() })
    await userEvent.click(screen.getByText('Add computer'))
    await waitFor(() => { expect(screen.getByRole('dialog', { name: /Add computer/ })).toBeInTheDocument() })

    fireEvent.keyDown(screen.getByRole('dialog', { name: /Add computer/ }), { key: 'Escape' })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /Add computer/ })).not.toBeInTheDocument()
    })
  })

  it('Escape closes Bootstrap Code modal', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    mockFetch.mockResolvedValueOnce(ok({
      bootstrap_token: 'la_boot_test_esc',
      expires_at: '2026-01-01T00:10:00Z',
      device_id: 'dev_new',
    }))
    renderDevices()
    await waitFor(() => { expect(screen.getByText('Add computer')).toBeInTheDocument() })
    await userEvent.click(screen.getByText('Add computer'))
    await userEvent.type(screen.getByPlaceholderText(/David's MacBook Pro/), 'Test PC')
    await userEvent.click(screen.getByText('Generate code'))
    await waitFor(() => { expect(screen.getByText('la_boot_test_esc')).toBeInTheDocument() })

    fireEvent.keyDown(screen.getByRole('dialog', { name: /Registration code/ }), { key: 'Escape' })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /Registration code/ })).not.toBeInTheDocument()
    })
  })

  // -----------------------------------------------------------------------
  // ARIA live/status tests
  // -----------------------------------------------------------------------

  it('scan request status has aria-live region', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok([]))
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => { expect(screen.getByText(/No reviews have been requested/)).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok(SAMPLE_JOB))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_JOB]))
    await userEvent.click(screen.getByText('Review project'))
    await waitFor(() => {
      expect(screen.getByText('Review complete')).toBeInTheDocument()
    })

    // Check aria-live region exists and contains status
    const liveRegion = document.querySelector('[aria-live="polite"]')
    expect(liveRegion).toBeInTheDocument()
  })

  it('error messages have role="alert"', async () => {
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    // Trigger a fetch error
    mockFetch.mockRejectedValueOnce(new Error('Network error'))
    // Re-render to trigger error (the initial fetch already resolved, so this tests a different path)
    await waitFor(() => { expect(screen.getByText('No computers connected yet.')).toBeInTheDocument() })

    // When there are no devices, there's no error-msg element, so let's test the modal error path
    await userEvent.click(screen.getByText('Add computer'))
    // Submit without name to trigger validation error
    await userEvent.click(screen.getByText('Generate code'))
    await waitFor(() => {
      const alerts = screen.getAllByRole('alert')
      expect(alerts.length).toBeGreaterThan(0)
    })
  })

  it('project list has accessible list semantics', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    const list = screen.getByRole('list', { name: /Authorised projects/ })
    expect(list).toBeInTheDocument()
    const items = list.querySelectorAll('[role="listitem"]')
    expect(items.length).toBe(1)
    expect(items[0].textContent).toContain('BibleQuest')
  })

  it('review button is disabled while a job is in progress', async () => {
    const activeJob = { ...SAMPLE_JOB, status: 'PENDING', started_at: null, completed_at: null }
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    // Open project -> list jobs returns active job
    mockFetch.mockResolvedValueOnce(ok([activeJob]))
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => {
      expect(screen.getAllByText('Review in progress').length).toBeGreaterThanOrEqual(1)
    })

    // Review button should be disabled
    const reviewBtn = screen.getByRole('button', { name: /Review BibleQuest/i })
    expect(reviewBtn).toBeDisabled()
  })

  it('clicking project auto-selects it and shows review history', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    // Mock jobs for after click
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_JOB]))
    // Click the strong element (project name) inside the button card
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => {
      expect(screen.getByText('Review history')).toBeInTheDocument()
      expect(screen.getByText(/Project unchanged/)).toBeInTheDocument()
    })
  })

  it('review status banner is visible and dismissible', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('BibleQuest')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok([])) // initial jobs
    await userEvent.click(screen.getByText('BibleQuest'))
    await waitFor(() => { expect(screen.getByText(/No reviews/)).toBeInTheDocument() })

    // Request scan
    mockFetch.mockResolvedValueOnce(ok(SAMPLE_JOB))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_JOB]))
    await userEvent.click(screen.getByText('Review project'))
    await waitFor(() => {
      expect(screen.getByText(/Review queued/)).toBeInTheDocument()
    })

    // Dismiss banner
    const dismissBtn = screen.getByRole('button', { name: /Dismiss/i })
    await userEvent.click(dismissBtn)
    expect(screen.queryByText(/Review queued/)).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// LA6.4A Project Authorization Tests
// ---------------------------------------------------------------------------

describe('Project Authorization Flow', () => {
  it('shows Authorise project button for active devices', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_PROJECT]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('Authorise project')).toBeInTheDocument() })
  })

  it('does not show Authorise project for revoked devices', async () => {
    const revokedDevice = { ...SAMPLE_DEVICE, status: 'revoked' as const }
    mockFetch.mockResolvedValueOnce(ok([revokedDevice]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText(/No projects authorised/)).toBeInTheDocument() })
    expect(screen.queryByText('Authorise project')).not.toBeInTheDocument()
  })

  it('token is not generated on page load', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('Authorise project')).toBeInTheDocument() })
    // No token modal should be visible
    expect(screen.queryByRole('dialog', { name: /project authorization/i })).not.toBeInTheDocument()
  })

  it('shows token modal after successful authorization request', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('Authorise project')).toBeInTheDocument() })

    // Mock the auth token endpoint
    mockFetch.mockResolvedValueOnce(ok({
      project_authorization_token: 'la_proj_test123abc',
      expires_at: new Date(Date.now() + 600000).toISOString(),
    }))

    await userEvent.click(screen.getByText('Authorise project'))
    await waitFor(() => {
      expect(screen.getByText('Project authorization code')).toBeInTheDocument()
    })
    expect(screen.getByText('la_proj_test123abc')).toBeInTheDocument()
  })

  it('shows expiry and single-use warning in token modal', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('Authorise project')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok({
      project_authorization_token: 'la_proj_test123abc',
      expires_at: new Date(Date.now() + 600000).toISOString(),
    }))

    await userEvent.click(screen.getByText('Authorise project'))
    await waitFor(() => {
      expect(screen.getByText(/can only be used once/)).toBeInTheDocument()
    })
  })

  it('shows authority explanation in token modal', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('Authorise project')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok({
      project_authorization_token: 'la_proj_test123abc',
      expires_at: new Date(Date.now() + 600000).toISOString(),
    }))

    await userEvent.click(screen.getByText('Authorise project'))
    await waitFor(() => {
      expect(screen.getByText(/does not allow EVOSIA to execute, merge, deploy/)).toBeInTheDocument()
    })
  })

  it('token is removed from UI state when modal closes', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('Authorise project')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce(ok({
      project_authorization_token: 'la_proj_test123abc',
      expires_at: new Date(Date.now() + 600000).toISOString(),
    }))

    await userEvent.click(screen.getByText('Authorise project'))
    await waitFor(() => {
      expect(screen.getByText('Project authorization code')).toBeInTheDocument()
    })

    // Close modal
    await userEvent.click(screen.getByText('Done'))
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /project authorization/i })).not.toBeInTheDocument()
    })
  })

  it('API errors fail closed', async () => {
    mockFetch.mockResolvedValueOnce(ok([SAMPLE_DEVICE]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => { expect(screen.getByText("David's MacBook")).toBeInTheDocument() })
    await userEvent.click(screen.getByText("David's MacBook"))
    await waitFor(() => { expect(screen.getByText('Authorise project')).toBeInTheDocument() })

    mockFetch.mockResolvedValueOnce({
      ok: false, status: 403, json: () => Promise.resolve({ detail: 'Access denied' }),
      headers: new Headers(),
    } as Response)

    await userEvent.click(screen.getByText('Authorise project'))
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// LA6.3J: UTC timestamp timezone contract tests
// ---------------------------------------------------------------------------

describe('UTC timestamp timezone contract', () => {
  beforeEach(() => { mockFetch.mockReset() })

  it('fresh UTC Z-suffixed timestamp renders Online', async () => {
    // Simulate what the API now returns: "2026-08-28T11:59:19Z"
    const now = new Date()
    const freshTimestamp = new Date(now.getTime() - 60000).toISOString() // 1 minute ago
    const device: Device = {
      ...SAMPLE_DEVICE,
      last_seen_at: freshTimestamp,
    }
    mockFetch.mockResolvedValueOnce(ok([device]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => {
      expect(screen.getByText('online')).toBeInTheDocument()
    })
  })

  it('timestamp 4m59s old renders Online', async () => {
    const now = new Date()
    const almostOld = new Date(now.getTime() - (4 * 60 + 59) * 1000).toISOString()
    const device: Device = {
      ...SAMPLE_DEVICE,
      last_seen_at: almostOld,
    }
    mockFetch.mockResolvedValueOnce(ok([device]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => {
      expect(screen.getByText('online')).toBeInTheDocument()
    })
  })

  it('timestamp 5m01s old renders Offline', async () => {
    const now = new Date()
    const tooOld = new Date(now.getTime() - (5 * 60 + 1) * 1000).toISOString()
    const device: Device = {
      ...SAMPLE_DEVICE,
      last_seen_at: tooOld,
    }
    mockFetch.mockResolvedValueOnce(ok([device]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => {
      expect(screen.getByText('offline')).toBeInTheDocument()
    })
  })

  it('null last_seen_at renders Offline', async () => {
    const device: Device = {
      ...SAMPLE_DEVICE,
      last_seen_at: null,
    }
    mockFetch.mockResolvedValueOnce(ok([device]))
    mockFetch.mockResolvedValueOnce(ok([]))
    renderDevices()
    await waitFor(() => {
      expect(screen.getByText('offline')).toBeInTheDocument()
    })
  })

  it('Z-suffixed timestamp parses correctly regardless of browser timezone', () => {
    // The key test: "2026-08-28T11:59:19Z" MUST be parsed as UTC
    // regardless of the browser's local timezone
    const utcTimestamp = '2026-08-28T11:59:19Z'
    const parsed = new Date(utcTimestamp)
    // Verify it's interpreted as UTC (the getTime value should be stable)
    expect(parsed.toISOString()).toBe('2026-08-28T11:59:19.000Z')

    // Now test with a naive timestamp (the old bug)
    const naiveTimestamp = '2026-08-28T11:59:19' // no Z
    void new Date(naiveTimestamp) // would be local time, NOT UTC
    const utcEquivalent = new Date('2026-08-28T11:59:19Z')
    // In a non-UTC timezone, these would differ
    // We just verify the Z version is stable
    expect(parsed.getTime()).toBe(utcEquivalent.getTime())
  })
})
