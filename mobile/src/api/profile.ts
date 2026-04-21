import { apiClient } from './client';

export interface ProfileCreateRequest {
  name?: string | null;
  sex: string;
  age: number;
  height_cm: number;
  weight_kg: number;
  activity_level: string;
  measurements?: Record<string, number | null> | null;
  training_days?: string[];
  sport_types?: string[];
  goal: string;
  allergies?: string[];
  disliked_foods?: string[];
  diet_type?: string | null;
  budget_rub_week?: number | null;
  cooking_frequency?: string;
  cooking_time_budget?: Record<string, number | string | null> | null;
  family_size?: number;
  kitchen_equipment?: string[];
  eating_schedule?: Record<string, any>;
  planned_deviations?: Array<{
    type: string;
    description: string;
    day_of_week: number | null;
    kcal_extra: number;
  }>;
  flexibility_pct?: number;
}

export interface ProfileResponse {
  id: number;
  user_id: number;
  name: string | null;
  goal: string | null;
  weight_kg: number | null;
  height_cm: number | null;
  age: number | null;
  activity_level: string | null;
  measurements: Record<string, number | null> | null;
  training_days: string[] | null;
  sport_types: string[] | null;
  target_kcal: number | null;
  target_protein_g: number | null;
  target_fat_g: number | null;
  target_carbs_g: number | null;
  eating_schedule: Record<string, any> | null;
  planned_deviations: Array<Record<string, unknown>> | null;
  flexibility_pct: number | null;
  sex: string | null;
  allergies: string[] | null;
  disliked_foods: string[] | null;
  budget_rub_week: number | null;
  diet_type: string | null;
  cooking_frequency: string | null;
  cooking_time_budget: Record<string, number | string | null> | null;
  family_size: number | null;
  kitchen_equipment: string[] | null;
}

export const profileApi = {
  onboarding: (data: ProfileCreateRequest) =>
    apiClient.post<ProfileResponse>('/profile/onboarding', data).then((r) => r.data),

  get: () =>
    apiClient.get<ProfileResponse>('/profile').then((r) => r.data),

  update: (data: Partial<ProfileCreateRequest>) =>
    apiClient.patch<ProfileResponse>('/profile', data).then((r) => r.data),
};
