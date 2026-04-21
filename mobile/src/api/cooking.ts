import { apiClient } from './client';

export const cookingApi = {
  getPlan: () =>
    apiClient.get('/cooking/plan').then((r) => r.data),

  markStepDone: (stepId: number) =>
    apiClient.post(`/cooking/steps/${stepId}/done`).then((r) => r.data),

  getContainerDistribution: () =>
    apiClient.get('/cooking/containers').then((r) => r.data),
};
