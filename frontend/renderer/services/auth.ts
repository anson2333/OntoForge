/**
 * Authentication store.
 * Keeps the session token in the SSP client and exposes the signed-in user.
 */

import { create } from 'zustand';
import { sspClient } from './ssp_client';

export interface AuthUser {
  user_id: string;
  username: string;
  display_name: string;
  roles: string[];
}

type AuthStatus = 'checking' | 'anonymous' | 'authenticated';

interface AuthState {
  status: AuthStatus;
  user: AuthUser | null;
  error: string | null;
  isSubmitting: boolean;

  bootstrap: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

async function fetchCurrentUser(): Promise<AuthUser | null> {
  try {
    const result = await sspClient.authStatus();
    return result?.authenticated ? (result.user as AuthUser) : null;
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  status: 'checking',
  user: null,
  error: null,
  isSubmitting: false,

  bootstrap: async () => {
    if (!sspClient.getToken()) {
      set({ status: 'anonymous', user: null });
      return;
    }
    const user = await fetchCurrentUser();
    if (user) {
      sspClient.setToken(sspClient.getToken());
      set({ status: 'authenticated', user, error: null });
    } else {
      sspClient.setToken(null);
      set({ status: 'anonymous', user: null });
    }
  },

  login: async (username, password) => {
    set({ isSubmitting: true, error: null });
    try {
      const session = await sspClient.login(username, password);
      sspClient.setToken(session.token);
      set({ status: 'authenticated', user: session.user, isSubmitting: false });
    } catch (error) {
      sspClient.setToken(null);
      set({
        status: 'anonymous',
        user: null,
        isSubmitting: false,
        error: error instanceof Error ? error.message : 'Login failed'
      });
      throw error;
    }
  },

  register: async (username, password, displayName) => {
    set({ isSubmitting: true, error: null });
    try {
      await sspClient.register(username, password, displayName);
      const session = await sspClient.login(username, password);
      sspClient.setToken(session.token);
      set({ status: 'authenticated', user: session.user, isSubmitting: false });
    } catch (error) {
      sspClient.setToken(null);
      set({
        status: 'anonymous',
        user: null,
        isSubmitting: false,
        error: error instanceof Error ? error.message : 'Registration failed'
      });
      throw error;
    }
  },

  logout: async () => {
    try {
      await sspClient.logout();
    } finally {
      sspClient.setToken(null);
      set({ status: 'anonymous', user: null, error: null });
    }
  },

  clearError: () => set({ error: null })
}));
