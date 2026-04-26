import { create } from 'zustand';
import { Platform } from 'react-native';
import { planApi, MealPlanResponse } from '@/api/plan';

const planStorage = {
  async save(key: string, value: string) {
    if (Platform.OS === 'web') {
      localStorage.setItem(key, value);
    } else {
      const SecureStore = require('expo-secure-store');
      await SecureStore.setItemAsync(key, value);
    }
  },
  async get(key: string): Promise<string | null> {
    if (Platform.OS === 'web') {
      return localStorage.getItem(key);
    }
    const SecureStore = require('expo-secure-store');
    return SecureStore.getItemAsync(key);
  },
  async remove(key: string) {
    if (Platform.OS === 'web') {
      localStorage.removeItem(key);
    } else {
      const SecureStore = require('expo-secure-store');
      await SecureStore.deleteItemAsync(key);
    }
  },
};

interface PlanState {
  plan: MealPlanResponse | null;
  planId: number | null;
  hasFetchedCurrent: boolean;
  loading: boolean;
  generating: boolean;
  replacingMealId: number | null;
  rebuildingDayId: number | null;
  error: string | null;
  fetchPlan: () => Promise<void>;
  generate: (notes?: string) => Promise<void>;
  replaceMeal: (mealId: number) => Promise<void>;
  rebuildDay: (dayId: number) => Promise<void>;
  markEaten: (mealId: number) => void;
  hydratePlan: () => Promise<void>;
  clearPlan: () => Promise<void>;
}

export const usePlanStore = create<PlanState>((set, get) => ({
  plan: null,
  planId: null,
  hasFetchedCurrent: false,
  loading: false,
  generating: false,
  replacingMealId: null,
  rebuildingDayId: null,
  error: null,

  hydratePlan: async () => {
    try {
      const stored = await planStorage.get('plan_id');
      if (stored) {
        set({ planId: parseInt(stored, 10) });
      }
    } catch {
      // storage unavailable; keep defaults
    }
  },

  fetchPlan: async () => {
    set({ loading: true, error: null });
    try {
      const data = await planApi.getCurrent();
      await planStorage.save('plan_id', String(data.id));
      set({ plan: data, planId: data.id, hasFetchedCurrent: true });
    } catch (e: any) {
      if (e?.response?.status === 404) {
        set({ plan: null, planId: null, hasFetchedCurrent: true });
        await planStorage.remove('plan_id');
      } else {
        set({ error: e?.message ?? 'Ошибка загрузки плана', hasFetchedCurrent: true });
      }
    } finally {
      set({ loading: false });
    }
  },

  generate: async (notes?: string) => {
    set({ generating: true, error: null });
    try {
      const { plan_id } = await planApi.generate({ use_ai: false, notes });
      await planStorage.save('plan_id', String(plan_id));
      set({ planId: plan_id });
      await get().fetchPlan();
    } catch (e: any) {
      set({ error: e?.response?.data?.detail ?? e?.message ?? 'Ошибка генерации плана' });
    } finally {
      set({ generating: false });
    }
  },

  replaceMeal: async (mealId: number) => {
    set({ replacingMealId: mealId, error: null });
    try {
      await planApi.replaceMeal(mealId);
      const data = await planApi.getCurrent();
      await planStorage.save('plan_id', String(data.id));
      set({ plan: data, planId: data.id, hasFetchedCurrent: true });
    } catch (e: any) {
      set({ error: e?.response?.data?.detail ?? e?.message ?? 'Не удалось заменить блюдо' });
    } finally {
      set({ replacingMealId: null });
    }
  },

  rebuildDay: async (dayId: number) => {
    set({ rebuildingDayId: dayId, error: null });
    try {
      await planApi.rebuildDay(dayId);
      const data = await planApi.getCurrent();
      await planStorage.save('plan_id', String(data.id));
      set({ plan: data, planId: data.id, hasFetchedCurrent: true });
    } catch (e: any) {
      set({ error: e?.response?.data?.detail ?? e?.message ?? 'Не удалось пересобрать день' });
    } finally {
      set({ rebuildingDayId: null });
    }
  },

  markEaten: (mealId) => {
    const plan = get().plan;
    if (!plan) return;
    set({
      plan: {
        ...plan,
        days: plan.days.map((d) => ({
          ...d,
          meals: d.meals.map((m) => (m.id === mealId ? { ...m, status: 'eaten' } : m)),
        })),
      },
    });
  },

  clearPlan: async () => {
    await planStorage.remove('plan_id');
    set({
      plan: null,
      planId: null,
      hasFetchedCurrent: false,
      loading: false,
      generating: false,
      replacingMealId: null,
      rebuildingDayId: null,
      error: null,
    });
  },
}));
