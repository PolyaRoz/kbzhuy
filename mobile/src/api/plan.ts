import { apiClient } from './client';

export interface PlanMeal {
  id: number;
  meal_type: string;
  meal_name?: string | null;
  meal_time?: string | null;
  container_id: number | null;
  container_label?: string | null;
  description?: string | null;
  recipe_details?: {
    serving_grams?: number | null;
    ingredients?: { name: string; quantity: number; unit: string }[];
    steps?: { order: number; text: string; time_min?: number | null }[];
  } | null;
  heating_instructions?: string | null;
  status: string;          // "planned" | "eaten" | "skipped"
  kbzhu_actual: { kcal: number; protein: number; fat: number; carbs: number } | null;
}

export interface PlanDay {
  id: number;
  date: string;            // ISO date "2026-04-14"
  meals: PlanMeal[];
}

export interface DailyTargets {
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
}

export interface MealPlanResponse {
  id: number;
  period_start: string;
  period_end: string;
  status: string;
  daily_targets: DailyTargets;
  days: PlanDay[];
}

export interface GenerateResponse {
  status: string;
  plan_id: number;
  source?: string;
  ai_reply?: string;
}

export interface GeneratePlanRequest {
  period_start?: string;
  period_end?: string;
  use_ai?: boolean;
  notes?: string;
}

export type MealStatus = 'planned' | 'eaten' | 'skipped';

// Returns the coming Monday (always in the future — plan is created for next week).
// Mon→+7, Tue→+6, Wed→+5, Thu→+4, Fri→+3, Sat→+2, Sun→+1
function nextMonday(): string {
  const d = new Date();
  const day = d.getDay(); // 0=Sun, 1=Mon
  const daysUntil = day === 0 ? 1 : 8 - day;
  d.setDate(d.getDate() + daysUntil);
  return d.toISOString().slice(0, 10);
}

export const planApi = {
  generate: (request: GeneratePlanRequest = {}): Promise<GenerateResponse> => {
    const period_start = request.period_start ?? nextMonday();
    const start = new Date(period_start);
    start.setDate(start.getDate() + 6);
    const period_end = request.period_end ?? start.toISOString().slice(0, 10);
    return apiClient.post<GenerateResponse>('/plan/generate', {
      period_start,
      period_end,
      use_ai: request.use_ai ?? false,
      notes: request.notes,
    }).then((r) => r.data);
  },

  getCurrent: (): Promise<MealPlanResponse> =>
    apiClient.get<MealPlanResponse>('/plan/current').then((r) => r.data),

  getByPeriod: (periodStart: string): Promise<MealPlanResponse> =>
    apiClient.get<MealPlanResponse>(`/plan/period/${periodStart}`).then((r) => r.data),

  patchDay: (dayId: number, data: object) =>
    apiClient.patch(`/plan/day/${dayId}`, data).then((r) => r.data),

  replaceMeal: (mealId: number) =>
    apiClient.post(`/plan/meal/${mealId}/replace`).then((r) => r.data),

  rebuildDay: (dayId: number) =>
    apiClient.post(`/plan/day/${dayId}/rebuild`).then((r) => r.data),

  updateMealStatus: (mealId: number, status: MealStatus) =>
    apiClient.patch(`/plan/meal/${mealId}/status`, { status }).then((r) => r.data),

  swapPreparedMeal: (mealId: number, targetMealId: number) =>
    apiClient.post(`/plan/meal/${mealId}/swap-prepared`, { target_meal_id: targetMealId }).then((r) => r.data),

  manualReplacement: (mealId: number, description: string) =>
    apiClient.post(`/plan/meal/${mealId}/manual-replacement`, { description }).then((r) => r.data),

  getDeviations: () =>
    apiClient.get('/plan/deviations').then((r) => r.data),
};
