"""
Nutri-engine: deterministic КБЖУ calculator.
No LLM — pure clinical formulas (Mifflin-St Jeor, WHO/FAO macros).
"""
from dataclasses import dataclass
from enum import Enum


class Goal(str, Enum):
    LOSS = "loss"           # похудение
    GAIN = "gain"           # набор
    MAINTAIN = "maintain"   # поддержание
    RECOMP = "recomp"       # рекомпозиция


class ActivityLevel(str, Enum):
    SEDENTARY = "sedentary"       # офис, нет спорта
    LIGHT = "light"               # 1-3 трен/нед
    MODERATE = "moderate"         # 3-5 трен/нед
    ACTIVE = "active"             # 6-7 трен/нед
    VERY_ACTIVE = "very_active"   # физический труд + спорт


ACTIVITY_MULTIPLIER = {
    ActivityLevel.SEDENTARY:   1.2,
    ActivityLevel.LIGHT:       1.375,
    ActivityLevel.MODERATE:    1.55,
    ActivityLevel.ACTIVE:      1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}

GOAL_KCAL_DELTA = {
    Goal.LOSS:     -500,   # ~0.5 кг/нед
    Goal.GAIN:     +400,
    Goal.MAINTAIN:   0,
    Goal.RECOMP:   -250,
}

# Protein targets (g per kg bodyweight) by goal
PROTEIN_PER_KG = {
    Goal.LOSS:     2.2,
    Goal.GAIN:     2.0,
    Goal.MAINTAIN: 1.8,
    Goal.RECOMP:   2.4,
}


@dataclass
class NutriTarget:
    kcal:    int
    protein: int   # г
    fat:     int   # г
    carbs:   int   # г
    bmr:     int
    tdee:    int


def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """Mifflin-St Jeor formula (kcal/day)."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def calculate_targets(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity: ActivityLevel,
    goal: Goal,
) -> NutriTarget:
    """
    Calculate personalised daily КБЖУ targets.

    Macro split:
    - Protein: goal-specific g/kg
    - Fat: 25-30% of kcal
    - Carbs: remainder
    """
    bmr  = calculate_bmr(weight_kg, height_cm, age, sex)
    tdee = bmr * ACTIVITY_MULTIPLIER[activity]
    kcal = round(tdee + GOAL_KCAL_DELTA[goal])

    protein_g = round(weight_kg * PROTEIN_PER_KG[goal])
    fat_g     = round(kcal * 0.27 / 9)          # 27% of kcal from fat
    protein_kcal = protein_g * 4
    fat_kcal     = fat_g * 9
    carbs_g   = round((kcal - protein_kcal - fat_kcal) / 4)

    return NutriTarget(
        kcal=kcal,
        protein=protein_g,
        fat=fat_g,
        carbs=max(carbs_g, 50),  # floor 50g carbs
        bmr=round(bmr),
        tdee=round(tdee),
    )


def apply_deviation_kcal(target: NutriTarget, deviation_kcal: int) -> NutriTarget:
    """
    Adjust targets when a planned deviation is registered.
    Spreads extra kcal by reducing carbs first, then fat.
    """
    new_kcal = target.kcal - deviation_kcal
    carbs_reduction = min(target.carbs - 50, deviation_kcal // 4)
    new_carbs = target.carbs - carbs_reduction
    remaining  = (deviation_kcal - carbs_reduction * 4) // 9
    new_fat    = max(target.fat - remaining, 30)
    return NutriTarget(
        kcal=new_kcal,
        protein=target.protein,
        fat=new_fat,
        carbs=new_carbs,
        bmr=target.bmr,
        tdee=target.tdee,
    )
