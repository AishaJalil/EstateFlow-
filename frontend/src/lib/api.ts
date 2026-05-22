import { supabase } from './supabase';
import { getVendorToken } from './vendorAuth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function getToken(): Promise<string | null> {
  const vendorToken = getVendorToken();
  if (vendorToken) return vendorToken;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  withAuth = true
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  if (withAuth) {
    const token = await getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const json = await res.json();
      message = (json as { detail?: string }).detail ?? JSON.stringify(json);
    } catch {
      message = (await res.text().catch(() => message)) || message;
    }
    throw new Error(message);
  }

  if (res.status === 204) return {} as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, withAuth = true) => request<T>(path, { method: 'GET' }, withAuth),
  post: <T>(path: string, body?: unknown, withAuth = true) =>
    request<T>(
      path,
      { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined },
      withAuth
    ),
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: 'POST', body: form }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
