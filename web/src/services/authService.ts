import { API_BASE } from '@/config';

export interface AuthUser {
  id: number;
  username: string;
}

export async function registerUser(username: string, email: string, password: string): Promise<AuthUser> {
  const body = {
    username,
    email,
    password,
  };

  const res = await fetch(`${API_BASE}/api/users`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => '');
    try {
      const data = JSON.parse(errorText) as { error?: string };
      if (data.error) throw new Error(data.error);
    } catch (e) {
      if (e instanceof Error && e.message !== errorText) throw e;
    }
    throw new Error(
      `Failed to register (status ${res.status}): ${errorText || res.statusText}`,
    );
  }

  const data = await res.json();
  const user = data.user as { id: number; username: string };
  return { id: user.id, username: user.username };
}

export async function loginUser(email: string, password: string): Promise<AuthUser> {
  const body = {
    username: email,
    password,
  };

  const res = await fetch(`${API_BASE}/api/users/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => '');
    try {
      const data = JSON.parse(errorText) as { error?: string };
      if (data.error) throw new Error(data.error);
    } catch (e) {
      if (e instanceof Error && e.message !== errorText) throw e;
    }
    throw new Error(
      `Failed to login (status ${res.status}): ${errorText || res.statusText}`,
    );
  }

  const data = await res.json();
  const user = data.user as { id: number; username: string };
  return { id: user.id, username: user.username };
}

export function setCurrentUser(user: AuthUser) {
  window.localStorage.setItem('currentUser', JSON.stringify(user));
}

export function getCurrentUser(): AuthUser | null {
  const raw = window.localStorage.getItem('currentUser');
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function clearCurrentUser() {
  window.localStorage.removeItem('currentUser');
}

