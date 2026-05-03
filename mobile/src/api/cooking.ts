import { apiClient } from './client';

export const cookingApi = {
  getPlan: () =>
    apiClient.get('/cooking/plan').then((r) => r.data),

  getPlanByPeriod: (periodStart: string) =>
    apiClient.get(`/cooking/plan/period/${periodStart}`).then((r) => r.data),

  generatePlan: () =>
    apiClient.post('/cooking/generate').then((r) => r.data),

  markStepDone: (stepId: number) =>
    apiClient.post(`/cooking/steps/${stepId}/done`).then((r) => r.data),

  setStepDone: (stepId: number, done: boolean) =>
    apiClient.patch(`/cooking/steps/${stepId}`, { done }).then((r) => r.data),

  getContainerDistribution: () =>
    apiClient.get('/cooking/containers').then((r) => r.data),
};
