import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { apiFetch, getToken } from '../lib/api'
import type { Repository, ScanJob, Finding } from '../lib/types'

const TABS = ['Overview', 'Scans', 'Findings'] as const;
type Tab = typeof TABS[number];

const STAGE_ORDER = [
  'metadata', 'materialization', 'readiness', 'repository_intelligence',
  'engineering_intelligence', 'governance', 'mission_recommendation',
  'persistence', 'journal',
];

export default function RepositoryDetailPage() {
  const { repoId } = useParams<{ repoId: string }>();
  const [repo, setRepo] = useState<Repository | null>(null);
  const [tab, setTab] = useState<Tab>('Overview');
  const [scans, setScans] = useState<ScanJob[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [selectedScan, setSelectedScan] = useState<ScanJob | null>(null);
  const [loading, setLoading] = useState(true);

  const token = getToken()!;

  useEffect(() => {
    if (!repoId) return;
    apiFetch<Repository>(`/repositories/${repoId}`, { token })
      .then(r => { setRepo(r); setLoading(false); });
  }, [repoId]);

  const fetchScans = useCallback(() => {
    if (!repoId) return;
    apiFetch<ScanJob[]>(`/scans?repository_id=${repoId}`, { token }).then(setScans);
  }, [repoId]);

  useEffect(() => { fetchScans(); }, [fetchScans]);

  useEffect(() => {
    if (tab === 'Findings' && repoId) {
      apiFetch<Finding[]>(`/findings?repository_id=${repoId}`, { token }).then(setFindings);
    }
  }, [tab, repoId]);

  const handleSync = async () => {
    if (!repoId) return;
    try {
      await apiFetch<Repository>(`/repositories/${repoId}/sync`, { token, method: 'POST' });
      const r = await apiFetch<Repository>(`/repositories/${repoId}`, { token });
      setRepo(r);
    } catch (e: any) {
      alert(e.message || 'Sync failed');
    }
  };

  const handleScan = async () => {
    if (!repoId) return;
    try {
      await apiFetch<ScanJob>('/scans', {
        token, method: 'POST',
        body: JSON.stringify({ repository_id: repoId }),
      });
      fetchScans();
    } catch (e: any) {
      alert(e.message || 'Scan creation failed');
    }
  };

  const handleCancel = async (id: string) => {
    if (!confirm('Cancel this scan?')) return;
    try {
      await apiFetch<ScanJob>(`/scans/${id}/cancel`, { token, method: 'POST' });
      fetchScans();
      if (selectedScan?.id === id) {
        const updated = await apiFetch<ScanJob>(`/scans/${id}`, { token });
        setSelectedScan(updated);
      }
    } catch (e: any) {
      alert(e.message || 'Cancel failed');
    }
  };

  const handleRetry = async (id: string) => {
    try {
      await apiFetch<ScanJob>(`/scans/${id}/retry`, { token, method: 'POST' });
      fetchScans();
      setSelectedScan(null);
    } catch (e: any) {
      alert(e.message || 'Retry failed');
    }
  };

  const openScanDetail = async (scan: ScanJob) => {
    setSelectedScan(scan);
  };

  if (loading) return <div className="empty-state">Loading...</div>;
  if (!repo) return <div className="empty-state">Repository not found</div>;

  return (
    <div>
      <div className="page-header">
        <h1>{repo.name}</h1>
        <p>{repo.url}</p>
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          {repo.provider === 'github' && (
            <button className="btn btn-sm" style={{ background: 'var(--bg-hover)', color: 'var(--text)' }} onClick={handleSync}>
              Sync
            </button>
          )}
          <button className="btn btn-sm" style={{ background: 'var(--accent)', color: 'white' }} onClick={handleScan}>
            Scan
          </button>
        </div>
      </div>

      <div className="tabs" style={{ display: 'flex', gap: 0, marginBottom: 24, borderBottom: '1px solid var(--border)' }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{
              padding: '10px 20px', background: 'none', border: 'none', color: tab === t ? 'var(--accent)' : 'var(--text-muted)',
              borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
              cursor: 'pointer', fontSize: 14, fontWeight: 500,
            }}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'Overview' && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="label">Provider</div>
            <div className="value" style={{ fontSize: 18 }}>{repo.provider}</div>
          </div>
          <div className="stat-card">
            <div className="label">Visibility</div>
            <div className="value" style={{ fontSize: 18 }}>{repo.visibility ?? '—'}</div>
          </div>
          <div className="stat-card">
            <div className="label">Branch</div>
            <div className="value" style={{ fontSize: 18 }}>{repo.default_branch}</div>
          </div>
          <div className="stat-card">
            <div className="label">Commit</div>
            <div className="value" style={{ fontSize: 12, fontFamily: 'monospace' }}>{repo.commit_sha?.slice(0, 8) ?? '—'}</div>
          </div>
          <div className="stat-card">
            <div className="label">Health</div>
            <div className={`value ${repo.health_score && repo.health_score >= 80 ? 'green' : repo.health_score && repo.health_score >= 60 ? 'yellow' : 'red'}`}>
              {repo.health_score ?? '—'}
            </div>
          </div>
          <div className="stat-card">
            <div className="label">Findings</div>
            <div className="value">{repo.findings_count}</div>
          </div>
          <div className="stat-card">
            <div className="label">Last Synced</div>
            <div className="value" style={{ fontSize: 14 }}>{repo.last_synced_at?.slice(0, 16) ?? 'Never'}</div>
          </div>
          <div className="stat-card">
            <div className="label">Last Scanned</div>
            <div className="value" style={{ fontSize: 14 }}>{repo.last_scanned_at?.slice(0, 16) ?? 'Never'}</div>
          </div>
        </div>
      )}

      {tab === 'Scans' && (
        <div style={{ display: 'flex', gap: 24 }}>
          <div style={{ flex: selectedScan ? '0 0 400px' : '1', minWidth: 0 }}>
            {scans.length === 0 ? (
              <div className="empty-state">No scans yet</div>
            ) : (
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th><th>Status</th><th>Stage</th><th>Attempt</th><th>Duration</th><th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scans.map(s => (
                      <tr key={s.id} style={{ cursor: 'pointer', background: selectedScan?.id === s.id ? 'var(--bg-hover)' : undefined }}
                        onClick={() => openScanDetail(s)}>
                        <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{s.id.slice(0, 8)}</td>
                        <td><span className={`badge badge-${s.status === 'completed' ? 'green' : s.status === 'failed' ? 'red' : s.status === 'running' ? 'blue' : s.status === 'cancelled' ? 'yellow' : 'gray'}`}>{s.status}</span></td>
                        <td>{s.current_stage ?? '—'}</td>
                        <td>{s.attempt}</td>
                        <td>{s.duration_seconds !== null ? `${s.duration_seconds.toFixed(1)}s` : '—'}</td>
                        <td onClick={e => e.stopPropagation()}>
                          {['pending', 'queued', 'running'].includes(s.status) && (
                            <button className="btn btn-sm" style={{ background: 'var(--red)', color: 'white', marginRight: 4 }} onClick={() => handleCancel(s.id)}>Cancel</button>
                          )}
                          {['failed', 'cancelled'].includes(s.status) && (
                            <button className="btn btn-sm" style={{ background: 'var(--accent)', color: 'white' }} onClick={() => handleRetry(s.id)}>Retry</button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {selectedScan && (
            <div style={{ flex: 1, minWidth: 300 }}>
              <div className="card" style={{ padding: 20 }}>
                <h3 style={{ fontSize: 16, marginBottom: 16 }}>Scan Timeline</h3>
                <div style={{ fontFamily: 'monospace', fontSize: 13 }}>
                  {STAGE_ORDER.map((stage, i) => {
                    const timing = selectedScan.stage_timings?.[stage];
                    const isCompleted = selectedScan.stages_completed?.includes(stage);
                    const isCurrent = selectedScan.current_stage === stage;
                    return (
                      <div key={stage} style={{ marginBottom: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{
                            display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                            background: isCompleted ? 'var(--green)' : isCurrent ? 'var(--accent)' : 'var(--border)',
                          }} />
                          <span style={{ color: isCompleted ? 'var(--green)' : isCurrent ? 'var(--accent)' : 'var(--text-muted)', textTransform: 'uppercase', fontSize: 11 }}>
                            {stage.replace(/_/g, ' ')}
                          </span>
                          {timing && (
                            <span style={{ color: 'var(--text-muted)', fontSize: 11, marginLeft: 'auto' }}>
                              {timing.duration_seconds?.toFixed(1)}s
                            </span>
                          )}
                        </div>
                        {i < STAGE_ORDER.length - 1 && (
                          <div style={{ marginLeft: 3, borderLeft: '1px solid var(--border)', height: 12 }} />
                        )}
                      </div>
                    );
                  })}
                </div>
                {selectedScan.error_message && (
                  <div style={{ marginTop: 16, padding: 12, background: '#991b1b22', borderRadius: 6, fontSize: 13, color: 'var(--red)' }}>
                    {selectedScan.error_message}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'Findings' && (
        findings.length === 0 ? <div className="empty-state">No findings</div> : (
          <div className="table-container">
            <table>
              <thead><tr><th>Severity</th><th>Category</th><th>Title</th><th>Status</th></tr></thead>
              <tbody>
                {findings.map(f => (
                  <tr key={f.id}>
                    <td><span className={`badge badge-${f.severity === 'critical' ? 'red' : f.severity === 'high' ? 'orange' : 'yellow'}`}>{f.severity}</span></td>
                    <td>{f.category}</td>
                    <td>{f.title}</td>
                    <td><span className={`badge badge-${f.status === 'open' ? 'yellow' : 'green'}`}>{f.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}
