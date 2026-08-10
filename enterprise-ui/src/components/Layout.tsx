import { NavLink } from 'react-router-dom'
import { useAuth } from '../App'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/repositories', label: 'Repositories' },
  { to: '/scans', label: 'Scans' },
  { to: '/journal', label: 'Journal' },
  { to: '/findings', label: 'Findings' },
  { to: '/missions', label: 'Missions' },
  { to: '/reports', label: 'Reports' },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-title">Hermes Enterprise</div>
        <nav>
          {links.map(l => (
            <NavLink key={l.to} to={l.to} end={l.to === '/'}>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ position: 'absolute', bottom: 24, left: 20, right: 20 }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
            {user?.name}
          </div>
          <button className="btn btn-sm" style={{ width: '100%', background: 'var(--bg-hover)', color: 'var(--text)' }} onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
