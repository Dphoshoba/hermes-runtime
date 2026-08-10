import { useState, useEffect } from 'react'
import { apiFetch, getToken } from '../lib/api'
import type { DashboardActivityV2, OvernightSummary } from '../lib/types'

export default function DashboardPage() {
  const [activity, setActivity] = useState<DashboardActivityV2 | null>(null);
  const [overnight, setOvernight] = useState<OvernightSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<{ name: string } | null>(null);

  useEffect(() => {
    const token = getToken()!;
    Promise.all([
      apiFetch<DashboardActivityV2>('/dashboard/activity-v2', { token }),
      apiFetch<OvernightSummary>('/dashboard/overnight', { token }),
      apiFetch<{ name: string }>('/auth/me', { token }),
    ]).then(([a, o, u]) => {
      setActivity(a);
      setOvernight(o);
      setUser(u);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="empty-state">Loading...</div>;
  if (!activity) return <div className="empty-state">Failed to load dashboard</div>;

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good Morning';
    if (h < 18) return 'Good Afternoon';
    return 'Good Evening';
  };

  return (
    <div>
      <div className="page-header">
        <h1>{greeting()} {user?.name?.split(' ')[0] || ''}</h1>
        <p>Engineering Command Center</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="label">Repositories</div>
          <div className="value accent">{activity.repositories_total}</div>
        </div>
        <div className="stat-card">
          <div className="label">Ready</div>
          <div className="value green">{activity.repositories_ready}</div>
        </div>
        <div className="stat-card">
          <div className="label">Blocked</div>
          <div className="value red">{activity.repositories_blocked}</div>
        </div>
        <div className="stat-card">
          <div className="label">Queued Scans</div>
          <div className="value yellow">{activity.scans_queued}</div>
        </div>
        <div className="stat-card">
          <div className="label">Running Scans</div>
          <div className="value accent">{activity.scans_running}</div>
        </div>
        <div className="stat-card">
          <div className="label">Completed Today</div>
          <div className="value green">{activity.scans_completed_since}</div>
        </div>
        <div className="stat-card">
          <div className="label">Failed Today</div>
          <div className="value red">{activity.scans_failed_since}</div>
        </div>
        <div className="stat-card">
          <div className="label">New Findings</div>
          <div className="value yellow">{activity.new_findings_since}</div>
        </div>
        <div className="stat-card">
          <div className="label">Approved Recs</div>
          <div className="value green">{activity.governance_approved_since}</div>
        </div>
        <div className="stat-card">
          <div className="label">Draft Missions</div>
          <div className="value">{activity.draft_missions_since}</div>
        </div>
        <div className="stat-card">
          <div className="label">Avg Health</div>
          <div className="value green">{activity.average_repository_health ?? '—'}</div>
        </div>
      </div>

      {overnight && (
        <div className="card" style={{ marginBottom: 24, padding: 20 }}>
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Overnight Summary</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 12 }}>
            {overnight.window_start.slice(0, 16)} — {overnight.window_end.slice(0, 16)}
          </p>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 14 }}>
            <span>{overnight.repositories_scanned} repos scanned</span>
            <span>{overnight.successful_scans} successful</span>
            <span style={{ color: 'var(--red)' }}>{overnight.failed_scans} failed</span>
            <span>{overnight.new_findings} new findings</span>
            <span>{overnight.governance_decisions} governance decisions</span>
            <span>{overnight.draft_missions} draft missions</span>
          </div>
          <p style={{ marginTop: 12, fontSize: 13, color: 'var(--text-muted)' }}>{overnight.summary}</p>
        </div>
      )}

      <h2 style={{ marginBottom: 16, fontSize: 18 }}>Recent Activity</h2>
      <div className="table-container">
        <ul className="activity-list">
          {activity.latest_activity.length === 0 && <li className="empty-state">No recent activity</li>}
          {activity.latest_activity.map(ev => (
            <li key={ev.id} className="activity-item">
              <span className="activity-time">{ev.timestamp.slice(0, 19)}</span>
              <span className="activity-type">{ev.event_type}</span>
              <span style={{ color: 'var(--text-muted)' }}>{ev.actor}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
