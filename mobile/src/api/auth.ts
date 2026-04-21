import { apiClient } from './client';

export interface LoginRequest { email: string; password: string }
export interface RegisterRequest { email: string; password: string }
export interface TokenResponse { access_token: string; refresh_token: string; token_type: string }

export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<TokenResponse>('/auth/login', data).then((r) => r.data),

  register: (data: RegisterRequest) =>
    apiClient.post<TokenResponse>('/auth/register', data).then((r) => r.data),

  refresh: (refresh_token: string) =>
    apiClient.post<TokenResponse>('/auth/refresh', { refresh_token }).then((r) => r.data),
};
