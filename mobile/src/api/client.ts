import axios from 'axios';

const BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// Auto-refresh on 401: retry the original request once with new tokens
let isRefreshing = false;
let pendingRequests: Array<(token: string) => void> = [];

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Skip refresh for auth endpoints or already retried requests
    if (
      error.response?.status !== 401 ||
      originalRequest._retry ||
      originalRequest.url?.startsWith('/auth/')
    ) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    if (isRefreshing) {
      // Queue this request until refresh completes
      return new Promise((resolve) => {
        pendingRequests.push((token: string) => {
          originalRequest.headers['Authorization'] = `Bearer ${token}`;
          resolve(apiClient(originalRequest));
        });
      });
    }

    isRefreshing = true;

    try {
      // Lazy import to avoid circular dependency
      const { useAuthStore } = require('@/store/authStore');
      const success = await useAuthStore.getState().refreshTokens();

      if (success) {
        const newToken = useAuthStore.getState().accessToken!;
        // Retry queued requests
        pendingRequests.forEach((cb) => cb(newToken));
        pendingRequests = [];
        // Retry original request
        originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      }
    } catch {
      // refresh failed — logout already called by refreshTokens
    } finally {
      isRefreshing = false;
      pendingRequests = [];
    }

    return Promise.reject(error);
  }
);
