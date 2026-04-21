import { apiClient } from './client';

export const prepTasksApi = {
  getToday: () =>
    apiClient.get('/prep-tasks/today').then((r) => r.data),

  markDone: (taskId: number) =>
    apiClient.post(`/prep-tasks/${taskId}/done`).then((r) => r.data),
};
