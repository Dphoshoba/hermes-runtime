import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch, getToken } from '../lib/api'
import type { Repository } from '../lib/types'

export default function RepositoriesPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const token = getToken()!;

  const fetchRepos = () => {
    apiFetch<Repository[]>('/repositories', { token })
      .then(setRepos)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchRepos(); }, []);

  const handleSync = async (e: React.MouseEvent, repoId: string) => {
    e.stopPropagation();
    try {
      await apiFetch<Repository>(`/repositories/${repoId}/sync`, { token, method: 'POST' });
      fetchRepos();
    } catch (err: any) {
      alert(err.message || 'Sync failed');
    }
  };

  const handleScan = async (e: React.MouseEvent, repoId: string) => {
    e.stopPropagation();
    try {
      await apiFetch('/scans', { token, method: 'POST', body: JSON.stringify({ repository_id: repoId }) });
    } catch (err: any) {
      alert(err.message || 'Scan failed');
    }
  };

  const healthBadge = (score: number | null) => {
    if (score === null) return <span className="badge badge-gray">—</span>;
    if (score >= 80) return <span className="badge badge-green">{score}</span>;
    if (score >= 60) return <span className="badge badge-yellow">{score}</span>;
    return <span className="badge badge-red">{score}</span>;
  };

  return (
    <div>
      <div className="page-header">
        <h1>Repositories</h1>
        <p>Registered repositories</p>
      </div>

      {loading ? <div className="empty-state">Loading...</div> : repos.length === 0 ? (
        <div className="empty-state">No repositories registered yet</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
          {repos.map(repo => (
            <div key={repo.id} className="stat-card" style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/repositories/${repo.id}`)}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{repo.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{repo.language ?? '—'}</div>
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  <span className={`badge badge-${repo.provider === 'github' ? 'blue' : 'gray'}`}>{repo.provider}</span>
                  {repo.visibility && <span className={`badge badge-${repo.visibility === 'public' ? 'green' : 'yellow'}`}>{repo.visibility}</span>}
                </div>
              </div>

              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
                <div>{repo.default_branch} {repo.commit_sha ? `· ${repo.commit_sha.slice(0, 7)}` : ''}</div>
              </div>

              <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                <span>Health: {healthBadge(repo.health_score)}</span>
                <span>Findings: {repo.findings_count}</span>
              </div>

              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
                <div>Synced: {repo.last_synced_at?.slice(0, 16) ?? 'Never'}</div>
                <div>Scanned: {repo.last_scanned_at?.slice(0, 16) ?? 'Never'}</div>
              </div>

              <div style={{ display: 'flex', gap: 8 }} onClick={e => e.stopPropagation()}>
                <button className="btn btn-sm" style={{ flex: 1, background: 'var(--bg-hover)', color: 'var(--text)' }}
                  onClick={() => navigate(`/repositories/${repo.id}`)}>
                  Open
                </button>
                {repo.provider === 'github' && (
                  <button className="btn btn-sm" style={{ flex: 1, background: 'var(--bg-hover)', color: 'var(--text)' }}
                    onClick={(e) => handleSync(e, repo.id)}>
                    Sync
                  </button>
                )}
                <button className="btn btn-sm" style={{ flex: 1, background: 'var(--accent)', color: 'white' }}
                  onClick={(e) => handleScan(e, repo.id)}>
                  Scan
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
