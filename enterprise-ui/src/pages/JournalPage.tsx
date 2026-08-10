import { useState, useEffect } from 'react'
import { apiFetch, getToken } from '../lib/api'
import type { JournalEvent } from '../lib/types'

const EVENT_TYPES = [
  '', 'readiness.assessed', 'readiness.blocked', 'repo.scanned', 'repo.analyzed',
  'engineering.analyzed', 'governance.decided', 'recommendation.generated',
  'recommendation.approved', 'recommendation.rejected', 'mission.created',
  'mission.planned', 'mission.started', 'mission.completed', 'mission.failed',
  'evidence.recorded', 'review.completed', 'health.checked',
];

export default function JournalPage() {
  const [events, setEvents] = useState<JournalEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('');
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: String(limit) });
    if (typeFilter) params.set('event_type', typeFilter);
    apiFetch<JournalEvent[]>(`/journal?${params}`, { token: getToken()! })
      .then(setEvents)
      .finally(() => setLoading(false));
  }, [typeFilter, limit]);

  const badgeForType = (t: string) => {
    if (t.startsWith('mission.')) return 'badge-blue';
    if (t.startsWith('readiness.')) return 'badge-green';
    if (t.startsWith('github.')) return 'badge-orange';
    if (t.startsWith('evidence.') || t.startsWith('review.')) return 'badge-yellow';
    return 'badge-gray';
  };

  return (
    <div>
      <div className="page-header">
        <h1>Journal</h1>
        <p>Append-only pipeline activity log</p>
      </div>

      <div className="filters">
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
          <option value="">All event types</option>
          {EVENT_TYPES.filter(Boolean).map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={limit} onChange={e => setLimit(Number(e.target.value))}>
          <option value={25}>25</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </select>
      </div>

      {loading ? <div className="empty-state">Loading...</div> : events.length === 0 ? (
        <div className="empty-state">No journal events</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Event Type</th>
                <th>Stage</th>
                <th>Actor</th>
              </tr>
            </thead>
            <tbody>
              {events.map(ev => (
                <tr key={ev.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{ev.timestamp.slice(0, 19)}</td>
                  <td><span className={`badge ${badgeForType(ev.event_type)}`}>{ev.event_type}</span></td>
                  <td>{ev.stage}</td>
                  <td>{ev.actor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
