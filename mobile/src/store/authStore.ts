import { create } from 'zustand';
import { Platform } from 'react-native';
import { apiClient } from '@/api/client';
import { authApi } from '@/api/auth';

// Token storage — SecureStore on native, localStorage on web
const tokenStorage = {
  async save(key: string, value: string) {
    if (Platform.OS === 'web') {
      localStorage.setItem(key, value);
    } else {
      const SecureStore = require('expo-secure-store');
      await SecureStore.setItemAsync(key, value);
    }
  },
  async get(key: string): Promise<string | null> {
    if (Platform.OS === 'web') {
      return localStorage.getItem(key);
    }
    const SecureStore = require('expo-secure-store');
    return SecureStore.getItemAsync(key);
  },
  async remove(key: string) {
    if (Platform.OS === 'web') {
      localStorage.removeItem(key);
    } else {
      const SecureStore = require('expo-secure-store');
      await SecureStore.deleteItemAsync(key);
    }
  },
};

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  onboardingCompleted: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshTokens: () => Promise<boolean>;
  hydrate: () => Promise<void>;
  setOnboardingCompleted: (value: boolean) => Promise<void>;
}

function applyTokens(access: string, refresh: string) {
  apiClient.defaults.headers.common['Authorization'] = `Bearer ${access}`;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isHydrated: false,
  onboardingCompleted: false,

  login: async (email, password) => {
    const data = await authApi.login({ email, password });
    applyTokens(data.access_token, data.refresh_token);
    await tokenStorage.save('access_token', data.access_token);
    await tokenStorage.save('refresh_token', data.refresh_token);
    // Check if profile exists to determine onboarding status
    let onboardingCompleted = false;
    try {
      await apiClient.get('/profile');
      onboardingCompleted = true;
      await tokenStorage.save('onboarding_completed', '1');
    } catch {
      // No profile yet — onboarding required
    }
    set({ accessToken: data.access_token, refreshToken: data.refresh_token, isAuthenticated: true, onboardingCompleted });
  },

  register: async (email, password) => {
    const data = await authApi.register({ email, password });
    applyTokens(data.access_token, data.refresh_token);
    await tokenStorage.save('access_token', data.access_token);
    await tokenStorage.save('refresh_token', data.refresh_token);
    set({ accessToken: data.access_token, refreshToken: data.refresh_token, isAuthenticated: true, onboardingCompleted: false });
  },

  logout: async () => {
    delete apiClient.defaults.headers.common['Authorization'];
    await tokenStorage.remove('access_token');
    await tokenStorage.remove('refresh_token');
    await tokenStorage.remove('onboarding_completed');
    set({ accessToken: null, refreshToken: null, isAuthenticated: false, onboardingCompleted: false });
  },

  refreshTokens: async () => {
    const { refreshToken } = get();
    if (!refreshToken) return false;
    try {
      const data = await authApi.refresh(refreshToken);
      applyTokens(data.access_token, data.refresh_token);
      await tokenStorage.save('access_token', data.access_token);
      await tokenStorage.save('refresh_token', data.refresh_token);
      set({ accessToken: data.access_token, refreshToken: data.refresh_token, isAuthenticated: true });
      return true;
    } catch {
      // Refresh failed — force logout
      await get().logout();
      return false;
    }
  },

  hydrate: async () => {
    try {
      const access = await tokenStorage.get('access_token');
      const refresh = await tokenStorage.get('refresh_token');
      if (access && refresh) {
        applyTokens(access, refresh);
        const flag = await tokenStorage.get('onboarding_completed');
        set({ accessToken: access, refreshToken: refresh, isAuthenticated: true, isHydrated: true, onboardingCompleted: flag === '1' });
      } else {
        set({ isHydrated: true });
      }
    } catch {
      // Storage unavailable — treat as unauthenticated
      set({ isHydrated: true });
    }
  },

  setOnboardingCompleted: async (value: boolean) => {
    if (value) {
      await tokenStorage.save('onboarding_completed', '1');
    } else {
      await tokenStorage.remove('onboarding_completed');
    }
    set({ onboardingCompleted: value });
  },
}));
