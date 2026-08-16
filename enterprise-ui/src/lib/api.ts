const API_BASE = '/api';

interface FetchOptions extends RequestInit {
  token?: string;
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { token, ...fetchOptions } = options;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function getToken(): string | undefined {
  return localStorage.getItem('evosia_token') ?? undefined;
}

export function setToken(token: string) {
  localStorage.setItem('evosia_token', token);
}

export function clearToken() {
  localStorage.removeItem('evosia_token');
}

// ---------------------------------------------------------------------------
// Guided Mode API client
// ---------------------------------------------------------------------------

export async function guidedApi<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const token = getToken();
  return apiFetch<T>(`/guided${path}`, { token, ...options }) as Promise<T>;
}

export const guidedClient = {
  async summary(repositoryId?: string): Promise<any> {
    const qs = repositoryId ? `?repository_id=${encodeURIComponent(repositoryId)}` : '';
    return guidedApi(`/summary${qs}`);
  },
  async needsAttention(repositoryId?: string): Promise<any> {
    const qs = repositoryId ? `?repository_id=${encodeURIComponent(repositoryId)}` : '';
    return guidedApi(`/needs-attention${qs}`);
  },
  async needsContext(repositoryId?: string): Promise<any> {
    const qs = repositoryId ? `?repository_id=${encodeURIComponent(repositoryId)}` : '';
    return guidedApi(`/needs-context${qs}`);
  },
  async missions(repositoryId?: string): Promise<any> {
    const qs = repositoryId ? `?repository_id=${encodeURIComponent(repositoryId)}` : '';
    return guidedApi(`/missions${qs}`);
  },
  async approvePreparation(missionId: string, operator: string): Promise<any> {
    return guidedApi(`/missions/${missionId}/approve-preparation`, {
      method: 'POST',
      body: JSON.stringify({ operator }),
    });
  },
  async prepareChange(missionId: string): Promise<any> {
    return guidedApi(`/missions/${missionId}/prepare`, { method: 'POST', body: JSON.stringify({}) });
  },
  async preparedChanges(repositoryId?: string): Promise<any> {
    const qs = repositoryId ? `?repository_id=${encodeURIComponent(repositoryId)}` : '';
    return guidedApi(`/prepared-changes${qs}`);
  },
  async getPreparedChange(preparedId: string): Promise<any> {
    return guidedApi(`/prepared-changes/${preparedId}`);
  },
  permission: () => guidedApi('/permission'),
  context: {
    list: (repositoryId?: string, topic?: string) => {
      const params = new URLSearchParams();
      if (repositoryId) params.set('repository_id', repositoryId);
      if (topic) params.set('topic', topic);
      const qs = params.toString();
      return guidedApi(`/context${qs ? `?${qs}` : ''}`);
    },
    add: (data: { topic: string; key: string; value: string; scope?: string; confidence?: string }) =>
      guidedApi('/context', { method: 'POST', body: JSON.stringify(data) }),
    remove: (contextId: string) => guidedApi(`/context/${contextId}`, { method: 'DELETE' }),
  },
};
