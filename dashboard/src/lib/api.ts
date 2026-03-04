/**
 * lib/api.ts — Typed API client for the FastAPI backend.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';

async function req<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Request failed');
  }
  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface TokenResponse { access_token: string; token_type: string; }
export interface UserOut { id: number; email: string; }

export const api = {
  // Auth
  register: (email: string, password: string) =>
    req<UserOut>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    req<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  // Devices
  listDevices: (token: string) =>
    req<Device[]>('/devices', {}, token),

  updateDevice: (token: string, id: number, data: Partial<DeviceUpdate>) =>
    req<Device>(`/dashboard/devices/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }, token),

  generatePairCode: (token: string) =>
    req<{ pair_code: string; expires_at: string }>('/pair-codes', {
      method: 'POST',
    }, token),

  // Events
  listEvents: (token: string, skip = 0, limit = 50) =>
    req<Event[]>(`/events?skip=${skip}&limit=${limit}`, {}, token),

  deleteAllEvents: (token: string) =>
    req<{ success: boolean; deleted: number }>('/events', {
      method: 'DELETE',
    }, token),

  // Telegram
  generateTelegramOtp: (token: string) =>
    req<{ otp: string; expires_at: string }>('/telegram/otp', {
      method: 'POST',
    }, token),
};

// ── Types ─────────────────────────────────────────────────────────────────────

export type ControlMode = 'BOTH' | 'DASHBOARD_ONLY' | 'TELEGRAM_ONLY';

export interface Device {
  id: number;
  name: string;
  armed: boolean;
  online: boolean;
  control_mode: ControlMode;
  snapshot_enabled: boolean;
  confidence_threshold: number;
  headless: boolean;
  last_seen_at: string | null;
  created_at: string;
}

export interface DeviceUpdate {
  name: string;
  armed: boolean;
  control_mode: ControlMode;
  snapshot_enabled: boolean;
  confidence_threshold: number;
  headless: boolean;
}

export interface Event {
  id: number;
  device_id: number;
  happened_at: string;
  created_at: string;
  confidence: number;
  image_filename: string | null;
}
