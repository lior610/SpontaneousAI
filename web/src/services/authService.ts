import { API_BASE } from '@/config';
import { throwApiError } from '@/lib/utils';

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
    await throwApiError(res, 'Failed to register');
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
    await throwApiError(res, 'Failed to login');
  }

  const data = await res.json();
  const user = data.user as { id: number; username: string };
  return { id: user.id, username: user.username };
}

export async function resetPassword(email: string, newPassword: string, confirmPassword: string): Promise<void> {
  const body = {
    email,
    new_password: newPassword,
    confirm_password: confirmPassword,
  };

  const res = await fetch(`${API_BASE}/api/users/reset-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    await throwApiError(res, 'Failed to reset password');
  }
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

