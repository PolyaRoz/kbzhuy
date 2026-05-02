import { apiClient } from './client';

export const shoppingApi = {
  getList: () =>
    apiClient.get('/shopping-list').then((r) => r.data),

  checkItem: (itemId: number, checked: boolean) =>
    apiClient.patch(`/shopping-list/items/${itemId}`, { checked }).then((r) => r.data),

  confirmItems: (itemIds: number[]) =>
    apiClient.post('/shopping-list/confirm', { item_ids: itemIds }).then((r) => r.data),

  markAll: () =>
    apiClient.post('/shopping-list/mark-all', { checked: true }).then((r) => r.data),
};
