import { Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect, createContext, useContext } from 'react'
import { apiFetch, getToken, setToken, clearToken } from './lib/api'
import type { User } from './lib/types'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import RepositoriesPage from './pages/RepositoriesPage'
import RepositoryDetailPage from './pages/RepositoryDetailPage'
import ScansPage from './pages/ScansPage'
import JournalPage from './pages/JournalPage'
import FindingsPage from './pages/FindingsPage'
import MissionsPage from './pages/MissionsPage'
import ReportsPage from './pages/ReportsPage'

interface AuthCtx {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthCtx>({ user: null, login: async () => {}, logout: () => {} });

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const token = getToken();
    if (token) {
      apiFetch<User>('/auth/me', { token })
        .then(setUser)
        .catch(() => clearToken());
    }
  }, []);

  const login = async (email: string, password: string) => {
    const res = await apiFetch<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setToken(res.access_token);
    const me = await apiFetch<User>('/auth/me', { token: res.access_token });
    setUser(me);
  };

  const logout = () => {
    clearToken();
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        <Route path="/repositories" element={<ProtectedRoute><RepositoriesPage /></ProtectedRoute>} />
        <Route path="/repositories/:repoId" element={<ProtectedRoute><RepositoryDetailPage /></ProtectedRoute>} />
        <Route path="/scans" element={<ProtectedRoute><ScansPage /></ProtectedRoute>} />
        <Route path="/journal" element={<ProtectedRoute><JournalPage /></ProtectedRoute>} />
        <Route path="/findings" element={<ProtectedRoute><FindingsPage /></ProtectedRoute>} />
        <Route path="/missions" element={<ProtectedRoute><MissionsPage /></ProtectedRoute>} />
        <Route path="/reports" element={<ProtectedRoute><ReportsPage /></ProtectedRoute>} />
      </Routes>
    </AuthProvider>
  );
}
