"""
Nutri-engine based on the nutrition materials in `Нутрициолог/Читаемая база`.

Documented rules:
  - Calories: Mifflin-St Jeor with activity coefficient.
  - Practical correction: use the average between the minimal (1.2) and
    the selected real activity coefficient.
  - Protein: 1.5-2.0 g/kg depending on activity/training context.
  - Fat: up to 30% of total calories.
  - Carbohydrates: calculated as the remainder after protein and fat.

Product goal policy:
  - maintain: corrected maintenance
  - loss: -10% calories
  - gain: +10% calories
  - recomp: -5% calories with higher protein
"""

from dataclasses import dataclass
from enum import Enum


class Goal(str, Enum):
    LOSS = "loss"
    GAIN = "gain"
    MAINTAIN = "maintain"
    RECOMP = "recomp"


class ActivityLevel(str, Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


ACTIVITY_MULTIPLIER = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.7,
    ActivityLevel.VERY_ACTIVE: 1.9,
}

MIN_ACTIVITY_MULTIPLIER = 1.2
FAT_SHARE_MAX = 0.30
GOAL_KCAL_FACTOR = {
    Goal.LOSS: 0.90,
    Goal.GAIN: 1.10,
    Goal.MAINTAIN: 1.00,
    Goal.RECOMP: 0.95,
}


@dataclass
class NutriTarget:
    kcal: int
    protein: int
    fat: int
    carbs: int
    bmr: int
    tdee: int


def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """Mifflin-St Jeor formula."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def _practical_activity_multiplier(activity: ActivityLevel) -> float:
    """
    Practical rule from the nutrition notes:
    take the average between the minimal and the real activity coefficient.
    """
    real = ACTIVITY_MULTIPLIER[activity]
    if real <= MIN_ACTIVITY_MULTIPLIER:
        return MIN_ACTIVITY_MULTIPLIER
    return (MIN_ACTIVITY_MULTIPLIER + real) / 2


def _protein_per_kg(goal: Goal, activity: ActivityLevel) -> float:
    """Protein targeting within the documented 1.5-2.0 g/kg range."""
    if goal == Goal.RECOMP:
        return 2.0

    if goal == Goal.GAIN:
        return 2.0 if activity in {ActivityLevel.MODERATE, ActivityLevel.ACTIVE, ActivityLevel.VERY_ACTIVE} else 1.8

    if goal == Goal.LOSS:
        if activity == ActivityLevel.SEDENTARY:
            return 1.6
        if activity == ActivityLevel.LIGHT:
            return 1.7
        return 1.8

    if activity == ActivityLevel.VERY_ACTIVE:
        return 2.0
    if activity == ActivityLevel.ACTIVE:
        return 1.8
    if activity == ActivityLevel.MODERATE:
        return 1.7
    if activity == ActivityLevel.LIGHT:
        return 1.6
    return 1.5


def calculate_targets(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity: ActivityLevel,
    goal: Goal,
) -> NutriTarget:
    """Calculate daily kcal and macros from the nutrition base plus goal policy."""
    bmr = calculate_bmr(weight_kg, height_cm, age, sex)
    activity_multiplier = _practical_activity_multiplier(activity)
    tdee = bmr * activity_multiplier
    kcal = round(tdee * GOAL_KCAL_FACTOR[goal])

    protein_g = round(weight_kg * _protein_per_kg(goal, activity))
    fat_g = round((kcal * FAT_SHARE_MAX) / 9)

    protein_kcal = protein_g * 4
    fat_kcal = fat_g * 9
    remaining_kcal = max(kcal - protein_kcal - fat_kcal, 0)
    carbs_g = round(remaining_kcal / 4)

    return NutriTarget(
        kcal=kcal,
        protein=protein_g,
        fat=fat_g,
        carbs=carbs_g,
        bmr=round(bmr),
        tdee=round(tdee),
    )


def apply_deviation_kcal(target: NutriTarget, deviation_kcal: int) -> NutriTarget:
    """
    Planned deviation reduces the available calories for the rest of the day.
    Reduction goes through carbohydrates first, then fats, while protein is kept.
    """
    new_kcal = max(target.kcal - deviation_kcal, 0)
    carbs_reduction = min(target.carbs, max(deviation_kcal, 0) // 4)
    new_carbs = max(target.carbs - carbs_reduction, 0)
    remaining_kcal = max(deviation_kcal - carbs_reduction * 4, 0)
    fat_reduction = remaining_kcal // 9
    new_fat = max(target.fat - fat_reduction, 0)
    return NutriTarget(
        kcal=new_kcal,
        protein=target.protein,
        fat=new_fat,
        carbs=new_carbs,
        bmr=target.bmr,
        tdee=target.tdee,
    )
