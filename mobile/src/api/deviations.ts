import { apiClient } from './client';

export type DeviationRegister = {
  deviation_type: 'planned' | 'spontaneous';
  date: string;
  description: string;
  kbzhu_impact?: { kcal: number; protein?: number; fat?: number; carbs?: number };
  recurrence?: string;
};

export const deviationsApi = {
  register: (data: DeviationRegister) =>
    apiClient.post('/deviations', data).then((r) => r.data),

  getPlanned: () =>
    apiClient.get('/deviations/planned').then((r) => r.data),

  recalc: (deviation_id: number) =>
    apiClient.post('/deviations/recalc', { deviation_id }).then((r) => r.data),
};
