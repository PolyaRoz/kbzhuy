import { apiClient } from './client';

export const storageApi = {
  getAll: () =>
    apiClient.get('/storage').then((r) => r.data),

  getExpiring: (days = 3) =>
    apiClient.get(`/storage/expiring?days=${days}`).then((r) => r.data),

  addContainer: (locationId: number, data: object) =>
    apiClient.post(`/storage/${locationId}/containers`, data).then((r) => r.data),

  updateContainer: (id: number, data: object) =>
    apiClient.patch(`/storage/containers/${id}`, data).then((r) => r.data),

  deleteContainer: (id: number) =>
    apiClient.delete(`/storage/containers/${id}`).then((r) => r.data),
};
