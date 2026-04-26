import { ProfileResponse } from '@/api/profile';

function sortedStrings(value: string[] | null | undefined) {
  return [...(value ?? [])].map((item) => item.trim()).filter(Boolean).sort();
}

function stable(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stable(item)).join(',')}]`;
  }
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    return `{${Object.keys(obj).sort().map((key) => `${key}:${stable(obj[key])}`).join(',')}}`;
  }
  return JSON.stringify(value ?? null);
}

export function shouldInvalidatePlan(previous: ProfileResponse | null, next: ProfileResponse | null) {
  if (!previous || !next) return true;

  const comparablePrevious = {
    sex: previous.sex,
    goal: previous.goal,
    weight_kg: previous.weight_kg,
    height_cm: previous.height_cm,
    age: previous.age,
    activity_level: previous.activity_level,
    measurements: previous.measurements ?? {},
    training_days: sortedStrings(previous.training_days),
    sport_types: sortedStrings(previous.sport_types),
    allergies: sortedStrings(previous.allergies),
    disliked_foods: sortedStrings(previous.disliked_foods),
    budget_rub_week: previous.budget_rub_week,
    diet_type: previous.diet_type,
    cooking_frequency: previous.cooking_frequency,
    cooking_time_budget: previous.cooking_time_budget ?? {},
    family_size: previous.family_size,
    kitchen_equipment: sortedStrings(previous.kitchen_equipment),
    eating_schedule: previous.eating_schedule ?? {},
    planned_deviations: previous.planned_deviations ?? [],
    flexibility_pct: previous.flexibility_pct,
  };

  const comparableNext = {
    sex: next.sex,
    goal: next.goal,
    weight_kg: next.weight_kg,
    height_cm: next.height_cm,
    age: next.age,
    activity_level: next.activity_level,
    measurements: next.measurements ?? {},
    training_days: sortedStrings(next.training_days),
    sport_types: sortedStrings(next.sport_types),
    allergies: sortedStrings(next.allergies),
    disliked_foods: sortedStrings(next.disliked_foods),
    budget_rub_week: next.budget_rub_week,
    diet_type: next.diet_type,
    cooking_frequency: next.cooking_frequency,
    cooking_time_budget: next.cooking_time_budget ?? {},
    family_size: next.family_size,
    kitchen_equipment: sortedStrings(next.kitchen_equipment),
    eating_schedule: next.eating_schedule ?? {},
    planned_deviations: next.planned_deviations ?? [],
    flexibility_pct: next.flexibility_pct,
  };

  return stable(comparablePrevious) !== stable(comparableNext);
}
