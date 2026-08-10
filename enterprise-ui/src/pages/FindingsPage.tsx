import { useState, useEffect } from 'react'
import { apiFetch, getToken } from '../lib/api'
import type { Finding } from '../lib/types'

export default function FindingsPage() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState('');

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: '100' });
    if (severityFilter) params.set('severity', severityFilter);
    apiFetch<Finding[]>(`/findings?${params}`, { token: getToken()! })
      .then(setFindings)
      .finally(() => setLoading(false));
  }, [severityFilter]);

  const severityBadge = (s: string) => {
    const m: Record<string, string> = { critical: 'badge-red', high: 'badge-orange', medium: 'badge-yellow', low: 'badge-gray' };
    return m[s] || 'badge-gray';
  };

  return (
    <div>
      <div className="page-header">
        <h1>Findings</h1>
        <p>Engineering findings from repository analysis</p>
      </div>

      <div className="filters">
        <select value={severityFilter} onChange={e => setSeverityFilter(e.target.value)}>
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {loading ? <div className="empty-state">Loading...</div> : findings.length === 0 ? (
        <div className="empty-state">No findings</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Category</th>
                <th>Title</th>
                <th>Module</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {findings.map(f => (
                <tr key={f.id}>
                  <td><span className={`badge ${severityBadge(f.severity)}`}>{f.severity}</span></td>
                  <td>{f.category}</td>
                  <td>{f.title}</td>
                  <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.module ?? '—'}</td>
                  <td><span className={`badge badge-${f.status === 'open' ? 'yellow' : 'green'}`}>{f.status}</span></td>
                  <td>{f.created_at.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
