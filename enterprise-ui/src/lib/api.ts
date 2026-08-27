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
// Device / Local Agent API client (LA5)
// ---------------------------------------------------------------------------

import type {
  Device, DeviceProject, AgentJob,
  DeviceRegisterResponse, ProjectAuthTokenResponse,
} from './types';

export const deviceClient = {
  list: () => apiFetch<Device[]>('/devices/', { token: getToken()! }),

  get: (deviceId: string) =>
    apiFetch<Device>(`/devices/${encodeURIComponent(deviceId)}`, { token: getToken()! }),

  register: (deviceName: string, platform: string, agentVersion: string) =>
    apiFetch<DeviceRegisterResponse>('/devices/register', {
      method: 'POST',
      token: getToken()!,
      body: JSON.stringify({ device_name: deviceName, platform, agent_version: agentVersion }),
    }),

  revoke: (deviceId: string) =>
    apiFetch<Device>(`/devices/${encodeURIComponent(deviceId)}/revoke`, {
      method: 'POST', token: getToken()!,
    }),

  createProjectAuthToken: (deviceId: string) =>
    apiFetch<ProjectAuthTokenResponse>(
      `/devices/${encodeURIComponent(deviceId)}/project-auth-token`,
      { method: 'POST', token: getToken()! },
    ),

  listProjects: (deviceId: string) =>
    apiFetch<DeviceProject[]>(
      `/device-projects/?device_id=${encodeURIComponent(deviceId)}`,
      { token: getToken()! },
    ),

  requestScan: (projectId: string) =>
    apiFetch<AgentJob>(`/device-projects/${encodeURIComponent(projectId)}/scans`, {
      method: 'POST',
      token: getToken()!,
      body: JSON.stringify({ operation_type: 'PROJECT_SCAN' }),
    }),

  listJobs: (projectId: string) =>
    apiFetch<AgentJob[]>(
      `/device-projects/${encodeURIComponent(projectId)}/jobs`,
      { token: getToken()! },
    ),

  revokeProject: (projectId: string) =>
    apiFetch<DeviceProject>(
      `/device-projects/${encodeURIComponent(projectId)}/revoke`,
      { method: 'POST', token: getToken()! },
    ),
};

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
  async reviewScope(repositoryId?: string): Promise<any> {
    const qs = repositoryId ? `?repository_id=${encodeURIComponent(repositoryId)}` : '';
    return guidedApi(`/review-scope${qs}`);
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
