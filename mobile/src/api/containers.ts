import { apiClient } from './client';

export const containersApi = {
  getCurrent: () =>
    apiClient.get('/containers/current').then((r) => r.data),

  getToday: () =>
    apiClient.get('/containers/today').then((r) => r.data),

  markEaten: (id: number) =>
    apiClient.post(`/containers/${id}/eaten`).then((r) => r.data),
};
