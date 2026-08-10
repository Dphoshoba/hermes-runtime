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
        <div className="empty-state">No missions</div>
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
