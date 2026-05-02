import { apiClient } from './client';

export const storageApi = {
  getAll: () =>
    apiClient.get('/storage').then((r) => r.data),

  getExpiring: async (_days: number) => [],

  addItem: (payload: { name: string; quantity: number; unit: string; location_type?: string | null; category?: string | null; raw?: boolean }) =>
    apiClient.post('/storage/items', payload).then((r) => r.data),

  useItem: (itemId: number, quantity: number) =>
    apiClient.post(`/storage/items/${itemId}/use`, { quantity }).then((r) => r.data),

  useByName: (payload: { name: string; quantity: number; unit: string }) =>
    apiClient.post('/storage/use-by-name', payload).then((r) => r.data),

  deleteItem: (itemId: number) =>
    apiClient.delete(`/storage/items/${itemId}`).then((r) => r.data),

  clearLocation: (locationType?: 'fridge' | 'freezer' | 'pantry') =>
    apiClient.delete('/storage/clear', { params: locationType ? { location_type: locationType } : {} }).then((r) => r.data),

  updateItem: (itemId: number, payload: { quantity?: number; unit?: string; location_type?: string }) =>
    apiClient.patch(`/storage/items/${itemId}`, payload).then((r) => r.data),
};
