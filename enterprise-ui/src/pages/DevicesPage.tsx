import { useState, useEffect, useCallback, useRef } from 'react'
import { deviceClient } from '../lib/api'
import type { Device, DeviceProject, AgentJob, DeviceRegisterResponse, ProjectAuthTokenResponse } from '../lib/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PLATFORM_LABELS: Record<string, string> = {
  macos: 'Mac', windows: 'Windows', linux: 'Linux',
}

function relativeTime(iso: string | null): string {
  if (!iso) return 'Never'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

function deviceStatus(device: Device): 'online' | 'offline' | 'revoked' {
  if (device.status === 'revoked') return 'revoked'
  if (!device.last_seen_at) return 'offline'
  const diff = Date.now() - new Date(device.last_seen_at).getTime()
  return diff < 5 * 60 * 1000 ? 'online' : 'offline'
}

const STATUS_BADGE: Record<string, string> = {
  online: 'badge-green', offline: 'badge-gray', revoked: 'badge-red',
}

const JOB_STATUS_LABEL: Record<string, string> = {
  QUEUED: 'Waiting for your computer',
  RUNNING: 'Reviewing project',
  COMPLETED: 'Review complete',
  PARTIAL: 'Completed with limits',
  FAILED: 'Review could not be completed',
  CANCELLED: 'Review cancelled',
  EXPIRED: 'Review request expired',
}

const JOB_STATUS_BADGE: Record<string, string> = {
  QUEUED: 'badge-gray', RUNNING: 'badge-blue',
  COMPLETED: 'badge-green', PARTIAL: 'badge-yellow',
  FAILED: 'badge-red', CANCELLED: 'badge-yellow', EXPIRED: 'badge-yellow',
}

// ---------------------------------------------------------------------------
// Modal focus management hook
// ---------------------------------------------------------------------------

function useModalFocusManagement(isOpen: boolean, onClose: () => void) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement as HTMLElement
      // Focus the first focusable element inside the modal after render
      const timer = setTimeout(() => {
        if (overlayRef.current) {
          const focusable = overlayRef.current.querySelector<HTMLElement>(
            'input, select, button, [tabindex]:not([tabindex="-1"])'
          )
          if (focusable) focusable.focus()
        }
      }, 0)
      return () => clearTimeout(timer)
    } else {
      // Restore focus when modal closes
      previousFocusRef.current?.focus()
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key === 'Tab' && overlayRef.current) {
        const focusable = overlayRef.current.querySelectorAll<HTMLElement>(
          'input, select, button, [tabindex]:not([tabindex="-1"])'
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  return overlayRef
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function EmptyDevices({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="empty-state">
      <p style={{ fontSize: 18, marginBottom: 8 }}>No computers connected yet.</p>
      <p style={{ marginBottom: 16 }}>Connect a computer to let EVOSIA review projects stored on it.</p>
      <button className="btn btn-primary" onClick={onAdd}>Add computer</button>
    </div>
  )
}

function AddComputerModal({ onClose, onCreated }: {
  onClose: () => void
  onCreated: (data: DeviceRegisterResponse) => void
}) {
  const [name, setName] = useState('')
  const [platform, setPlatform] = useState('macos')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const overlayRef = useModalFocusManagement(true, onClose)

  const handleSubmit = async () => {
    if (!name.trim()) { setError('Name is required'); return }
    setLoading(true); setError('')
    try {
      const res = await deviceClient.register(name.trim(), platform, 'unreported')
      onCreated(res)
    } catch (e: any) {
      setError(e.message || 'Failed to create registration code')
    } finally { setLoading(false) }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-label="Add computer" ref={overlayRef}>
      <div className="card" style={{ maxWidth: 480, width: '100%' }}>
        <h2 style={{ marginTop: 0 }}>Add computer</h2>
        <p className="muted">Generate a one-time registration code for a new computer.</p>

        <label style={{ display: 'block', marginBottom: 12 }}>
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Computer name</span>
          <input
            className="input"
            style={{ width: '100%', marginTop: 4 }}
            placeholder="e.g. David's MacBook Pro"
            value={name}
            onChange={e => setName(e.target.value)}
          />
        </label>

        <label style={{ display: 'block', marginBottom: 16 }}>
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Platform</span>
          <select
            className="input"
            style={{ width: '100%', marginTop: 4 }}
            value={platform}
            onChange={e => setPlatform(e.target.value)}
          >
            <option value="macos">Mac</option>
            <option value="windows">Windows</option>
            <option value="linux">Linux</option>
          </select>
        </label>

        {error && <p className="error-msg" role="alert">{error}</p>}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn btn-sm" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
            {loading ? 'Creating...' : 'Generate code'}
          </button>
        </div>
      </div>
    </div>
  )
}

function BootstrapCodeModal({ data, onClose }: {
  data: DeviceRegisterResponse
  onClose: () => void
}) {
  const overlayRef = useModalFocusManagement(true, onClose)

  return (
    <div className="modal-overlay" role="dialog" aria-label="Registration code" ref={overlayRef}>
      <div className="card" style={{ maxWidth: 520, width: '100%' }}>
        <h2 style={{ marginTop: 0 }}>Registration code ready</h2>
        <p className="muted" style={{ marginBottom: 16 }}>
          On the computer you want to connect, start EVOSIA Agent and enter this one-time code.
        </p>

        <div style={{
          background: 'var(--bg)', border: '1px solid var(--border)',
          borderRadius: 8, padding: '16px 20px', marginBottom: 12,
          fontFamily: 'monospace', fontSize: 18, letterSpacing: 1,
          textAlign: 'center', wordBreak: 'break-all',
        }}>
          {data.bootstrap_token}
        </div>

        <p className="muted" style={{ fontSize: 12 }}>
          Expires at {new Date(data.expires_at).toLocaleTimeString()}.
          This code can only be used once.
        </p>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <button className="btn btn-primary" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  )
}

function ProjectAuthTokenModal({ data, onClose }: {
  data: ProjectAuthTokenResponse
  onClose: () => void
}) {
  const overlayRef = useModalFocusManagement(true, onClose)
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(data.project_authorization_token)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* ignore */ }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-label="Project authorization token" ref={overlayRef}>
      <div className="card" style={{ maxWidth: 520, width: '100%' }}>
        <h2 style={{ marginTop: 0 }}>Project authorization code</h2>
        <p className="muted" style={{ marginBottom: 16 }}>
          On the computer you want to connect, run the following command with this code:
        </p>

        <div style={{
          background: 'var(--bg)', border: '1px solid var(--border)',
          borderRadius: 8, padding: '16px 20px', marginBottom: 12,
          fontFamily: 'monospace', fontSize: 14, letterSpacing: 0.5,
          wordBreak: 'break-all', userSelect: 'all',
        }}>
          {data.project_authorization_token}
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <button className="btn btn-primary" onClick={handleCopy}>
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>

        <p className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
          Expires at {new Date(data.expires_at).toLocaleTimeString()}. This code can only be used once.
        </p>
        <p className="muted" style={{ fontSize: 12 }}>
          This allows this computer to connect one project for review.
          It does not allow EVOSIA to execute, merge, deploy, or modify the project.
        </p>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <button className="btn btn-primary" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  )
}

function ReviewStatusBanner({ status, onDismiss }: { status: string; onDismiss: () => void }) {
  if (!status) return null
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        padding: '10px 16px', borderRadius: 8, marginBottom: 16,
        background: 'var(--accent-bg, #e8f4fd)', border: '1px solid var(--accent-border, #b3d8f0)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13,
      }}
    >
      <span>{status}</span>
      <button
        onClick={onDismiss}
        style={{
          background: 'none', border: 'none', cursor: 'pointer', fontSize: 16,
          color: 'var(--text-muted)', padding: '0 4px', lineHeight: 1,
        }}
        aria-label="Dismiss"
      >
        &times;
      </button>
    </div>
  )
}

function DeviceDetail({ device, onBack }: { device: Device; onBack: () => void }) {
  const [projects, setProjects] = useState<DeviceProject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedProject, setSelectedProject] = useState<DeviceProject | null>(null)
  const [jobs, setJobs] = useState<AgentJob[]>([])
  const [jobsLoadedProjectId, setJobsLoadedProjectId] = useState('')
  const [jobsLoading, setJobsLoading] = useState(false)
  const [jobsError, setJobsError] = useState('')
  const [requestingScan, setRequestingScan] = useState(false)
  const [cancellingJobId, setCancellingJobId] = useState('')
  const [scanBanner, setScanBanner] = useState('')
  const [scanError, setScanError] = useState('')
  const [authTokenData, setAuthTokenData] = useState<ProjectAuthTokenResponse | null>(null)
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const requestingScanRef = useRef(false)
  const jobsLoadRequestRef = useRef(0)
  const revokeRef = useRef(false)
  const authRef = useRef(false)

  useEffect(() => {
    deviceClient.listProjects(device.device_id)
      .then(setProjects)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [device.device_id])

  const loadJobs = useCallback(async (projectId: string) => {
    const requestId = ++jobsLoadRequestRef.current
    setJobsLoading(true)
    setJobsError('')
    try {
      const j = await deviceClient.listJobs(projectId)
      if (requestId === jobsLoadRequestRef.current) {
        setJobs(j)
        setJobsLoadedProjectId(projectId)
      }
    } catch (e: any) {
      if (requestId === jobsLoadRequestRef.current) {
        setJobsError(e.message || 'Unable to load review history')
      }
    } finally {
      if (requestId === jobsLoadRequestRef.current) setJobsLoading(false)
    }
  }, [])

  const handleSelectProject = (project: DeviceProject) => {
    if (selectedProject?.id === project.id) {
      jobsLoadRequestRef.current += 1
      setSelectedProject(null)
      setJobs([])
      setJobsLoadedProjectId('')
      setJobsLoading(false)
      setJobsError('')
      return
    }
    setSelectedProject(project)
    setJobs([])
    setJobsLoadedProjectId('')
    void loadJobs(project.id)
  }

  // Poll for active jobs (PENDING/STARTED) every 10s, stop when terminal
  useEffect(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    if (!selectedProject) return
    const hasActive = jobs.some(j => j.status === 'QUEUED' || j.status === 'RUNNING')
    if (!hasActive) return
    pollRef.current = setInterval(() => { loadJobs(selectedProject.id) }, 10_000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [selectedProject, jobs, loadJobs])

  const handleRequestScan = async (project: DeviceProject) => {
    if (
      requestingScanRef.current
      || selectedProject?.id !== project.id
      || jobsLoadedProjectId !== project.id
      || jobsLoading
      || jobsError
      || hasActiveJob(project.id)
      || project.status !== 'active'
      || st === 'revoked'
    ) return
    requestingScanRef.current = true
    // Auto-select the project so Review history section renders
    setSelectedProject(project)
    setRequestingScan(true)
    setScanBanner('Requesting review...')
    setScanError('')
    try {
      const job = await deviceClient.requestScan(project.id)
      setJobs(previous => [job, ...previous.filter(existing => existing.id !== job.id)])
      await loadJobs(project.id)
      setScanBanner('Review queued — your computer will process it shortly.')
    } catch (e: any) {
      setScanBanner('')
      setScanError(e.message || 'Failed to request review')
    } finally { setRequestingScan(false); requestingScanRef.current = false }
  }

  const handleCancelReview = async (projectId: string, jobId: string) => {
    if (!confirm('Cancel this computer review?')) return
    setCancellingJobId(jobId)
    setScanError('')
    try {
      await deviceClient.cancelJob(projectId, jobId)
      await loadJobs(projectId)
      setScanBanner('Review cancelled.')
    } catch (e: any) {
      setScanError(e.message || 'Failed to cancel review')
    } finally { setCancellingJobId('') }
  }

  const handleRevoke = async () => {
    if (revokeRef.current) return
    if (!confirm(`Revoke ${device.device_name}? EVOSIA will no longer accept work from this computer.`)) return
    revokeRef.current = true
    try {
      await deviceClient.revoke(device.device_id)
      onBack()
    } catch (e: any) { alert(e.message || 'Revoke failed') }
    finally { revokeRef.current = false }
  }

  const handleAuthorize = async () => {
    if (authRef.current) return
    authRef.current = true
    setAuthLoading(true)
    setAuthError('')
    try {
      const data = await deviceClient.createProjectAuthToken(device.device_id)
      setAuthTokenData(data)
    } catch (e: any) {
      setAuthError(e.message || 'Failed to generate authorization code')
    } finally { setAuthLoading(false); authRef.current = false }
  }

  const hasActiveJob = (projectId: string) =>
    jobs.some(j => j.device_project_id === projectId && (j.status === 'QUEUED' || j.status === 'RUNNING'))

  const st = deviceStatus(device)

  return (
    <div>
      <button className="btn btn-sm" style={{ marginBottom: 16, background: 'var(--bg-hover)', color: 'var(--text)' }} onClick={onBack}>
        &larr; All computers
      </button>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 22 }}>{device.device_name}</h1>
            <p className="muted" style={{ margin: '4px 0 0' }}>
              {PLATFORM_LABELS[device.platform] || device.platform} &middot; {device.agent_version}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className={`badge ${STATUS_BADGE[st]}`}>{st}</span>
            {device.status !== 'revoked' && (
              <button className="btn btn-sm" style={{ background: 'var(--red)', color: 'white' }} onClick={handleRevoke}>
                Revoke
              </button>
            )}
          </div>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          Last connected: {relativeTime(device.last_seen_at)}
        </p>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>Authorised projects</h2>
          {device.status !== 'revoked' && (
            <button
              className="btn btn-primary"
              style={{ fontSize: 13 }}
              disabled={authLoading}
              onClick={handleAuthorize}
            >
              {authLoading ? 'Generating...' : 'Authorise project'}
            </button>
          )}
        </div>

        {authError && <p className="error-msg" role="alert" style={{ marginBottom: 8 }}>{authError}</p>}

        {loading ? <p className="muted">Loading projects...</p> : error ? (
          <p className="error-msg" role="alert">{error}</p>
        ) : projects.length === 0 ? (
          <p className="muted">No projects authorised on this computer yet.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} role="list" aria-label="Authorised projects">
            {projects.map(p => {
              const activeJob = hasActiveJob(p.id)
              return (
                <div
                  key={p.id}
                  className="card"
                  role="listitem"
                  style={{
                    padding: 16, textAlign: 'left', width: '100%',
                    border: selectedProject?.id === p.id ? '1px solid var(--accent)' : undefined,
                    background: 'var(--card-bg, var(--bg))',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <button
                        type="button"
                        className="btn btn-sm"
                        style={{
                          background: 'transparent', border: 0, padding: 0,
                          color: 'inherit', fontSize: 14, textAlign: 'left',
                        }}
                        onClick={() => handleSelectProject(p)}
                        aria-pressed={selectedProject?.id === p.id}
                        aria-label={`Show review history for ${p.display_name}`}
                      >
                        <strong>{p.display_name}</strong>
                      </button>
                      <span className="muted" style={{ marginLeft: 8 }}>
                        {p.authority === 'REVIEW_ONLY' ? 'Review only' : p.authority}
                      </span>
                      {activeJob && (
                        <span className="badge badge-blue" style={{ marginLeft: 8, fontSize: 11 }}>
                          Review in progress
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      {p.status === 'revoked' && <span className="badge badge-red">Revoked</span>}
                      {p.status === 'active' && (
                        <button
                          className="btn btn-primary"
                          style={{ fontSize: 13 }}
                          disabled={
                            requestingScan
                            || selectedProject?.id !== p.id
                            || jobsLoadedProjectId !== p.id
                            || jobsLoading
                            || Boolean(jobsError)
                            || st === 'revoked'
                            || activeJob
                          }
                          onClick={() => handleRequestScan(p)}
                          aria-label={`Review ${p.display_name}`}
                        >
                          {requestingScan ? 'Requesting...' : jobsLoading && selectedProject?.id === p.id ? 'Loading review history...' : jobsError && selectedProject?.id === p.id ? 'Review history unavailable' : activeJob ? 'Review in progress' : selectedProject?.id !== p.id ? 'Select project first' : 'Review project'}
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="muted" style={{ margin: '4px 0 0', fontSize: 12 }}>
                    EVOSIA may inspect this project when you request a review.
                    It cannot modify files, execute code, commit, push, merge or deploy it.
                  </p>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {scanBanner && <ReviewStatusBanner status={scanBanner} onDismiss={() => setScanBanner('')} />}
      {scanError && (
        <div
          role="alert"
          style={{
            padding: '10px 16px', borderRadius: 8, marginBottom: 16,
            background: 'var(--red-bg, #fef2f2)', border: '1px solid var(--red-border, #fecaca)',
            fontSize: 13, color: 'var(--red)',
          }}
        >
          {scanError}
        </div>
      )}

      {selectedProject && (
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: 16 }}>Review history</h2>
          <p className="muted" style={{ marginBottom: 12 }}>
            {selectedProject.display_name}
          </p>

          {jobsError && (
            <div role="alert" className="error-msg" style={{ marginBottom: 12 }}>
            {jobsError}{' '}
            <button className="btn btn-sm" onClick={() => loadJobs(selectedProject.id)}>Retry</button>
            </div>
          )}

          {jobsLoading && jobs.length === 0 ? <p className="muted">Loading reviews...</p> : jobs.length === 0 ? (
            <p className="muted">No reviews have been requested for this project yet.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {jobs.map(j => (
                <div key={j.id} className="card" style={{ padding: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span className={`badge ${JOB_STATUS_BADGE[j.status] || 'badge-gray'}`}>
                        {JOB_STATUS_LABEL[j.truncated && j.status === 'COMPLETED' ? 'PARTIAL' : j.status] || j.status}
                      </span>
                      <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
                        {j.created_at ? new Date(j.created_at).toLocaleString() : ''}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {(j.completed_at || j.cancelled_at) && (
                        <span className="muted" style={{ fontSize: 12 }}>
                          finished {new Date(j.completed_at || j.cancelled_at!).toLocaleString()}
                        </span>
                      )}
                      {j.status === 'COMPLETED' && (
                        <span style={{ color: 'var(--green)', fontSize: 13, fontWeight: 500 }}>
                          &#10003; Project unchanged
                        </span>
                      )}
                    </div>
                  </div>
                  {j.status === 'FAILED' && j.failure_reason && (
                    <p className="error-msg" style={{ marginTop: 4, fontSize: 12 }}>{j.failure_reason}</p>
                  )}
                  {(j.status === 'PARTIAL' || j.truncated) && (
                    <div style={{
                      marginTop: 8, padding: '8px 12px', borderRadius: 6,
                      background: 'var(--yellow-bg, #fef3cd)', border: '1px solid var(--yellow-border, #ffc107)',
                      fontSize: 12,
                    }} role="status">
                      <strong>Completed with limits.</strong>{' '}
                      {j.coverage ? (
                        <>
                          Examined {j.coverage.files_examined} of {j.coverage.files_discovered} discovered files;
                          {' '}{j.coverage.files_skipped} skipped.
                          {j.coverage.limits_reached.length > 0 && (
                            <> Limits reached: {j.coverage.limits_reached.join(', ')}.</>
                          )}
                          {Object.keys(j.coverage.skip_reasons).length > 0 && (
                            <> Skip reasons: {Object.entries(j.coverage.skip_reasons).map(([reason, count]) => `${reason} (${count})`).join(', ')}.</>
                          )}
                        </>
                      ) : 'Some files may not have been examined.'}
                    </div>
                  )}
                  {j.coverage && j.status !== 'PARTIAL' && (
                    <p className="muted" style={{ margin: '4px 0 0', fontSize: 12 }}>
                      Coverage: {j.coverage.files_examined} of {j.coverage.files_discovered} files examined; {j.coverage.files_skipped} skipped.
                      {Object.keys(j.coverage.skip_reasons).length > 0 && (
                        <> Skip reasons: {Object.entries(j.coverage.skip_reasons).map(([reason, count]) => `${reason} (${count})`).join(', ')}.</>
                      )}
                    </p>
                  )}
                  {(j.status === 'COMPLETED' || j.status === 'PARTIAL') && (
                    <p className="muted" style={{ margin: '4px 0 0', fontSize: 12 }}>
                      EVOSIA inspected the project without modifying files, executing code, committing, pushing, merging or deploying anything.
                    </p>
                  )}
                  {(j.status === 'QUEUED' || j.status === 'RUNNING') && (
                    <button
                      className="btn btn-sm"
                      style={{ marginTop: 8, background: 'var(--red)', color: 'white' }}
                      disabled={cancellingJobId === j.id}
                      onClick={() => handleCancelReview(selectedProject.id, j.id)}
                    >
                      {cancellingJobId === j.id ? 'Cancelling...' : 'Cancel review'}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {authTokenData && (
        <ProjectAuthTokenModal data={authTokenData} onClose={() => setAuthTokenData(null)} />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [bootstrapData, setBootstrapData] = useState<DeviceRegisterResponse | null>(null)
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null)

  const fetchDevices = useCallback(() => {
    deviceClient.list()
      .then(setDevices)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetchDevices() }, [fetchDevices])

  // Poll device list every 30s so last_seen_at / online status stays current
  useEffect(() => {
    const id = setInterval(fetchDevices, 30_000)
    return () => clearInterval(id)
  }, [fetchDevices])

  if (selectedDevice) {
    // Refresh device data when returning from detail
    const fresh = devices.find(d => d.id === selectedDevice.id) || selectedDevice
    return <DeviceDetail device={fresh} onBack={() => { setSelectedDevice(null); fetchDevices() }} />
  }

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1>Computers</h1>
            <p>Devices connected to EVOSIA</p>
          </div>
          {devices.length > 0 && (
            <button className="btn btn-primary" onClick={() => setShowAdd(true)}>Add computer</button>
          )}
        </div>
      </div>

      {loading ? <div className="empty-state">Loading computers...</div>
        : error ? <p className="error-msg" role="alert">{error}</p>
        : devices.length === 0 ? <EmptyDevices onAdd={() => setShowAdd(true)} />
        : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} role="list" aria-label="Computers">
            {devices.map(d => {
              const st = deviceStatus(d)
              return (
                <button
                  key={d.id}
                  type="button"
                  className="card"
                  role="listitem"
                  style={{ cursor: 'pointer', padding: 16, textAlign: 'left', width: '100%', background: 'var(--card-bg, var(--bg))' }}
                  onClick={() => setSelectedDevice(d)}
                  aria-label={`${d.device_name}, ${st}`}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong style={{ fontSize: 15 }}>{d.device_name}</strong>
                      <span className="muted" style={{ marginLeft: 8 }}>
                        {PLATFORM_LABELS[d.platform] || d.platform} &middot; {d.agent_version}
                      </span>
                    </div>
                    <span className={`badge ${STATUS_BADGE[st]}`}>{st}</span>
                  </div>
                  <p className="muted" style={{ margin: '4px 0 0', fontSize: 12 }}>
                    Last connected: {relativeTime(d.last_seen_at)}
                  </p>
                </button>
              )
            })}
          </div>
        )
      }

      {showAdd && (
        <AddComputerModal
          onClose={() => setShowAdd(false)}
          onCreated={(data) => { setShowAdd(false); setBootstrapData(data) }}
        />
      )}

      {bootstrapData && (
        <BootstrapCodeModal data={bootstrapData} onClose={() => setBootstrapData(null)} />
      )}
    </div>
  )
}
