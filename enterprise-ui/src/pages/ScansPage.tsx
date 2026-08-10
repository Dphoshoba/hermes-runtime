import { useState, useEffect } from 'react'
import { apiFetch, getToken } from '../lib/api'
import type { ScanJob } from '../lib/types'

const STATUS_COLORS: Record<string, string> = {
  pending: 'badge-gray', queued: 'badge-gray', running: 'badge-blue',
  completed: 'badge-green', failed: 'badge-red', cancelled: 'badge-yellow',
};

export default function ScansPage() {
  const [scans, setScans] = useState<ScanJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  const fetchScans = () => {
    const params = new URLSearchParams({ limit: '100' });
    if (statusFilter) params.set('status', statusFilter);
    apiFetch<ScanJob[]>(`/scans?${params}`, { token: getToken()! })
      .then(setScans)
      .finally(() => setLoading(false));
  };

  useEffect(() => { setLoading(true); fetchScans(); }, [statusFilter]);

  const handleCancel = async (id: string) => {
    if (!confirm('Cancel this scan?')) return;
    try {
      await apiFetch<ScanJob>(`/scans/${id}/cancel`, { token: getToken()!, method: 'POST' });
      fetchScans();
    } catch (e: any) {
      alert(e.message || 'Cancel failed');
    }
  };

  const handleRetry = async (id: string) => {
    try {
      await apiFetch<ScanJob>(`/scans/${id}/retry`, { token: getToken()!, method: 'POST' });
      fetchScans();
    } catch (e: any) {
      alert(e.message || 'Retry failed');
    }
  };

  const fmtDuration = (s: number | null) => s !== null ? `${s.toFixed(1)}s` : '—';
  const fmtTime = (t: string | null) => t ? t.slice(0, 19) : '—';

  return (
    <div>
      <div className="page-header">
        <h1>Scans</h1>
        <p>Repository scan jobs and history</p>
      </div>

      <div className="filters">
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {loading ? <div className="empty-state">Loading...</div> : scans.length === 0 ? (
        <div className="empty-state">No scan jobs</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Scan ID</th>
                <th>Status</th>
                <th>Stage</th>
                <th>Attempt</th>
                <th>Started</th>
                <th>Finished</th>
                <th>Duration</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {scans.map(s => (
                <tr key={s.id}>
                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{s.id.slice(0, 8)}</td>
                  <td><span className={`badge ${STATUS_COLORS[s.status] || 'badge-gray'}`}>{s.status}</span></td>
                  <td>{s.current_stage ?? '—'}</td>
                  <td>{s.attempt}</td>
                  <td>{fmtTime(s.started_at)}</td>
                  <td>{fmtTime(s.completed_at)}</td>
                  <td>{fmtDuration(s.duration_seconds)}</td>
                  <td>
                    {['pending', 'queued', 'running'].includes(s.status) && (
                      <button className="btn btn-sm" style={{ background: 'var(--red)', color: 'white', marginRight: 8 }} onClick={() => handleCancel(s.id)}>
                        Cancel
                      </button>
                    )}
                    {['failed', 'cancelled'].includes(s.status) && (
                      <button className="btn btn-sm" style={{ background: 'var(--accent)', color: 'white' }} onClick={() => handleRetry(s.id)}>
                        Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
