import { apiClient } from './client';

export const shoppingApi = {
  getList: () =>
    apiClient.get('/shopping-list').then((r) => r.data),

  checkItem: (itemId: number, checked: boolean) =>
    apiClient.patch(`/shopping-list/items/${itemId}`, { checked }).then((r) => r.data),
};
