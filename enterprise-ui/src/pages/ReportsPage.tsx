import { useState, useEffect } from 'react'
import { apiFetch, getToken } from '../lib/api'
import type { Report } from '../lib/types'

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<Report[]>('/reports?limit=100', { token: getToken()! })
      .then(setReports)
      .finally(() => setLoading(false));
  }, []);

  const statusBadge = (s: string) => {
    const m: Record<string, string> = { COMPLETED: 'badge-green', FAILED: 'badge-red', PARTIAL: 'badge-yellow' };
    return m[s] || 'badge-gray';
  };

  return (
    <div>
      <div className="page-header">
        <h1>Reports</h1>
        <p>Mission execution reports</p>
      </div>

      {loading ? <div className="empty-state">Loading...</div> : reports.length === 0 ? (
        <div className="empty-state reports-empty-state">
          <h3>No reports yet</h3>
          <p>Reports provide a record of EVOSIA's reviews, findings, decisions and outcomes.</p>
          <div className="example-report" data-testid="example-report">
            <h4>Example report</h4>
            <div className="card">
              <strong>Project review summary</strong>
              <p className="muted">4 files examined · 1 issue requiring attention · 3 questions requiring context</p>
            </div>
            <p className="example-label">EXAMPLE ONLY — not live EVOSIA evidence.</p>
          </div>
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Tasks</th>
                <th>Completed</th>
                <th>Failed</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {reports.map(r => (
                <tr key={r.id}>
                  <td><strong>{r.title}</strong></td>
                  <td><span className={`badge ${statusBadge(r.status)}`}>{r.status}</span></td>
                  <td>{r.duration_seconds !== null ? `${r.duration_seconds.toFixed(1)}s` : '—'}</td>
                  <td>{r.tasks_planned ?? '—'}</td>
                  <td>{r.tasks_completed ?? '—'}</td>
                  <td>{r.tasks_failed ?? '—'}</td>
                  <td>{r.created_at.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
