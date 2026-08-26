import { useState, useEffect } from 'react'
import { apiFetch, getToken } from '../lib/api'
import type { Mission } from '../lib/types'

export default function MissionsPage() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: '100' });
    if (statusFilter) params.set('status', statusFilter);
    apiFetch<Mission[]>(`/missions?${params}`, { token: getToken()! })
      .then(setMissions)
      .finally(() => setLoading(false));
  }, [statusFilter]);

  const statusBadge = (s: string) => {
    const m: Record<string, string> = { pending: 'badge-yellow', running: 'badge-blue', completed: 'badge-green', failed: 'badge-red' };
    return m[s] || 'badge-gray';
  };

  return (
    <div>
      <div className="page-header">
        <h1>Missions</h1>
        <p>Mission queue and execution status</p>
      </div>

      <div className="filters">
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {loading ? <div className="empty-state">Loading...</div> : missions.length === 0 ? (
        <div className="empty-state missions-empty-state">
          <h3>No missions yet</h3>
          <p>Missions will appear here when work progresses into EVOSIA's mission workflow.</p>
          <div className="example-mission" data-testid="example-mission">
            <h4>Example mission</h4>
            <div className="card">
              <strong>Replace hardcoded API key with environment configuration</strong>
              <p className="muted">Read the API key from an environment variable instead of a hardcoded module constant.</p>
            </div>
            <p className="example-label">EXAMPLE ONLY — not a live EVOSIA mission.</p>
          </div>
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {missions.map(m => (
                <tr key={m.id}>
                  <td><strong>{m.title}</strong></td>
                  <td>{m.mission_type}</td>
                  <td><span className={`badge ${statusBadge(m.status)}`}>{m.status}</span></td>
                  <td>{m.priority}</td>
                  <td>{m.created_at.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
