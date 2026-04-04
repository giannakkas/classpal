import { create } from 'zustand';
import { api } from '@/lib/api';
import type { User, TokenResponse } from '@/types';

interface AuthState {
  user: User | null;
  loading: boolean;
  initialized: boolean;

  initialize: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: false,
  initialized: false,

  initialize: async () => {
    if (!api.isAuthenticated()) {
      set({ initialized: true, loading: false });
      return;
    }
    try {
      set({ loading: true });
      const user = await api.get<User>('/api/auth/me');
      set({ user, initialized: true, loading: false });
    } catch {
      api.clearTokens();
      set({ user: null, initialized: true, loading: false });
    }
  },

  login: async (email, password) => {
    set({ loading: true });
    try {
      const tokens = await api.post<TokenResponse>('/api/auth/login', { email, password });
      api.setTokens(tokens);
      const user = await api.get<User>('/api/auth/me');
      set({ user, loading: false });
    } catch (e) {
      set({ loading: false });
      throw e;
    }
  },

  register: async (email, password, fullName) => {
    set({ loading: true });
    try {
      const tokens = await api.post<TokenResponse>('/api/auth/register', {
        email,
        password,
        full_name: fullName,
      });
      api.setTokens(tokens);
      const user = await api.get<User>('/api/auth/me');
      set({ user, loading: false });
    } catch (e) {
      set({ loading: false });
      throw e;
    }
  },

  logout: () => {
    api.clearTokens();
    set({ user: null });
    window.location.href = '/auth';
  },
}));
