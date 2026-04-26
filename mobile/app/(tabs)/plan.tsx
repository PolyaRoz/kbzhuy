import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuthStore } from '../../src/store/authStore';
import { usePlanStore } from '../../src/store/planStore';

const PRIMARY = '#1A7340';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';
const RED = '#DC2626';

type DayTotals = {
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
};

const MONTH_SHORT = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
const DAY_SHORT = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
const DAY_FULL = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];

function formatShortDate(iso?: string | null) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return `${d.getDate()} ${MONTH_SHORT[d.getMonth()]}`;
}

function formatDayShort(iso?: string | null) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return DAY_SHORT[d.getDay()];
}

function formatDayFull(iso?: string | null) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return DAY_FULL[d.getDay()];
}

function totalsFromMeals(meals: Array<any>): DayTotals {
  return meals.reduce<DayTotals>(
    (acc, meal) => {
      const actual = meal?.kbzhu_actual;
      if (!actual) return acc;
      return {
        kcal: acc.kcal + Number(actual.kcal ?? 0),
        protein: acc.protein + Number(actual.protein ?? 0),
        fat: acc.fat + Number(actual.fat ?? 0),
        carbs: acc.carbs + Number(actual.carbs ?? 0),
      };
    },
    { kcal: 0, protein: 0, fat: 0, carbs: 0 },
  );
}

export function ErrorBoundary({ error, retry }: { error: Error; retry: () => void }) {
  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.center}>
        <Text style={styles.errorTitle}>Не удалось открыть план</Text>
        <Text style={styles.errorText}>{error?.message ?? 'Ошибка экрана плана'}</Text>
        <TouchableOpacity style={styles.secondaryButton} onPress={retry} activeOpacity={0.8}>
          <Text style={styles.secondaryButtonText}>Повторить</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

export default function PlanScreen() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const onboardingCompleted = useAuthStore((state) => state.onboardingCompleted);

  const plan = usePlanStore((state) => state.plan);
  const hasFetchedCurrent = usePlanStore((state) => state.hasFetchedCurrent);
  const loading = usePlanStore((state) => state.loading);
  const generating = usePlanStore((state) => state.generating);
  const replacingMealId = usePlanStore((state) => state.replacingMealId);
  const rebuildingDayId = usePlanStore((state) => state.rebuildingDayId);
  const error = usePlanStore((state) => state.error);

  const [selectedIdx, setSelectedIdx] = useState(0);
  const [expandedMealId, setExpandedMealId] = useState<number | null>(null);
  const autoGenerateAttempted = useRef(false);

  useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      autoGenerateAttempted.current = false;
      setSelectedIdx(0);
      setExpandedMealId(null);
      void usePlanStore.getState().clearPlan();
      return;
    }

    autoGenerateAttempted.current = false;
    setSelectedIdx(0);
    setExpandedMealId(null);
  }, [accessToken, isAuthenticated]);

  useEffect(() => {
    if (!hasFetchedCurrent) {
      autoGenerateAttempted.current = false;
    }
  }, [hasFetchedCurrent]);

  useEffect(() => {
    if (!isAuthenticated || !accessToken) return;
    if (hasFetchedCurrent || loading) return;

    void usePlanStore.getState().fetchPlan();
  }, [accessToken, hasFetchedCurrent, isAuthenticated, loading]);

  useEffect(() => {
    if (!isAuthenticated || !onboardingCompleted) return;
    if (!hasFetchedCurrent || loading || generating || error || plan) return;
    if (autoGenerateAttempted.current) return;

    autoGenerateAttempted.current = true;
    void usePlanStore.getState().generate();
  }, [isAuthenticated, onboardingCompleted, hasFetchedCurrent, loading, generating, error, plan]);

  if (loading && !plan) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={PRIMARY} />
          <Text style={styles.loadingText}>Загружаем план...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!plan) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <Text style={styles.emptyTitle}>Плана пока нет</Text>
          <Text style={styles.emptyText}>Откройте вкладку еще раз или создайте меню по вашему профилю.</Text>
          {error ? <Text style={styles.errorText}>{error}</Text> : null}
          <TouchableOpacity
            style={[styles.primaryButton, generating && styles.buttonDisabled]}
            onPress={() => void usePlanStore.getState().generate()}
            disabled={generating}
            activeOpacity={0.8}
          >
            {generating ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.primaryButtonText}>Создать план</Text>}
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const days = Array.isArray(plan.days) ? plan.days : [];
  const safeSelectedIdx = days.length === 0 ? 0 : Math.min(selectedIdx, days.length - 1);
  const selectedDay = days[safeSelectedIdx];
  const meals = Array.isArray(selectedDay?.meals) ? selectedDay.meals : [];
  const totals = totalsFromMeals(meals);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Text style={styles.title}>План на неделю</Text>
          <Text style={styles.period}>
            {formatShortDate(plan.period_start)} — {formatShortDate(plan.period_end)}
          </Text>
        </View>

        {error ? <Text style={styles.errorBanner}>{error}</Text> : null}

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.daysRow}>
          {days.map((day, idx) => (
            <TouchableOpacity
              key={day.id}
              style={[styles.dayChip, idx === safeSelectedIdx && styles.dayChipActive]}
              onPress={() => setSelectedIdx(idx)}
              activeOpacity={0.75}
            >
              <Text style={[styles.dayChipShort, idx === safeSelectedIdx && styles.dayChipShortActive]}>{formatDayShort(day.date)}</Text>
              <Text style={[styles.dayChipDate, idx === safeSelectedIdx && styles.dayChipDateActive]}>{new Date(day.date).getDate()}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        <View style={styles.dayHeader}>
          <Text style={styles.dayTitle}>
            {formatDayFull(selectedDay?.date)}, {formatShortDate(selectedDay?.date)}
          </Text>
          <Text style={styles.dayMeta}>{meals.length} приёма</Text>
        </View>

        {meals.length === 0 ? (
          <View style={styles.emptyMealsCard}>
            <Text style={styles.emptyMealsText}>На этот день пока нет блюд.</Text>
          </View>
        ) : (
          meals.map((meal) => (
            <View key={meal.id} style={styles.mealCard}>
              <View style={styles.mealContent}>
                <Text style={styles.mealMeta}>
                  {meal.meal_time ?? '—'} · {meal.meal_name ?? meal.meal_type ?? 'Приём пищи'}
                </Text>
                <Text style={styles.mealTitle}>{meal.description ?? 'Блюдо без названия'}</Text>
                <Text style={styles.mealKcal}>{Math.round(Number(meal?.kbzhu_actual?.kcal ?? 0))} ккал</Text>

                {meal.recipe_details ? (
                  <TouchableOpacity
                    style={[styles.recipeToggle, expandedMealId === meal.id && styles.recipeToggleOpen]}
                    onPress={() => setExpandedMealId(expandedMealId === meal.id ? null : meal.id)}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.recipeToggleText}>Рецепт</Text>
                    <Text style={styles.recipeToggleArrow}>{expandedMealId === meal.id ? '▲' : '▼'}</Text>
                  </TouchableOpacity>
                ) : null}

                {expandedMealId === meal.id && meal.recipe_details ? (
                  <View style={styles.recipeBox}>
                    {meal.recipe_details.serving_grams ? (
                      <Text style={styles.recipeMeta}>Порция: {meal.recipe_details.serving_grams} г</Text>
                    ) : null}

                    {Array.isArray(meal.recipe_details.ingredients) && meal.recipe_details.ingredients.length > 0 ? (
                      <>
                        <Text style={styles.recipeSectionTitle}>Ингредиенты</Text>
                        {meal.recipe_details.ingredients.map((ingredient, index) => (
                          <Text key={`${meal.id}-ingredient-${index}`} style={styles.recipeLine}>
                            {ingredient.name} — {ingredient.quantity} {ingredient.unit}
                          </Text>
                        ))}
                      </>
                    ) : null}

                    {Array.isArray(meal.recipe_details.steps) && meal.recipe_details.steps.length > 0 ? (
                      <>
                        <Text style={styles.recipeSectionTitle}>Рецепт</Text>
                        {meal.recipe_details.steps.map((step, index) => (
                          <Text key={`${meal.id}-step-${index}`} style={styles.recipeLine}>
                            {step.order}. {step.text}
                          </Text>
                        ))}
                      </>
                    ) : null}
                  </View>
                ) : null}
              </View>

              <TouchableOpacity
                style={[styles.smallButton, replacingMealId === meal.id && styles.buttonDisabled]}
                onPress={() => void usePlanStore.getState().replaceMeal(meal.id)}
                disabled={Boolean(replacingMealId) || Boolean(rebuildingDayId) || generating}
                activeOpacity={0.8}
              >
                {replacingMealId === meal.id ? <ActivityIndicator color={PRIMARY} size="small" /> : <Text style={styles.smallButtonText}>Заменить</Text>}
              </TouchableOpacity>
            </View>
          ))
        )}

        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Итого за день</Text>
          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryValue}>{Math.round(totals.kcal)}</Text>
              <Text style={styles.summaryLabel}>Ккал</Text>
            </View>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryValue}>{Math.round(totals.protein)} г</Text>
              <Text style={styles.summaryLabel}>Белок</Text>
            </View>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryValue}>{Math.round(totals.fat)} г</Text>
              <Text style={styles.summaryLabel}>Жир</Text>
            </View>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryValue}>{Math.round(totals.carbs)} г</Text>
              <Text style={styles.summaryLabel}>Углев.</Text>
            </View>
          </View>
        </View>

        {selectedDay ? (
          <TouchableOpacity
            style={[styles.secondaryButton, rebuildingDayId === selectedDay.id && styles.buttonDisabled]}
            onPress={() => void usePlanStore.getState().rebuildDay(selectedDay.id)}
            disabled={Boolean(replacingMealId) || Boolean(rebuildingDayId) || generating}
            activeOpacity={0.8}
          >
            {rebuildingDayId === selectedDay.id ? <ActivityIndicator color={PRIMARY} size="small" /> : <Text style={styles.secondaryButtonText}>Пересобрать день</Text>}
          </TouchableOpacity>
        ) : null}

        <TouchableOpacity
          style={[styles.primaryOutlineButton, generating && styles.buttonDisabled]}
          onPress={() => void usePlanStore.getState().generate()}
          disabled={generating}
          activeOpacity={0.8}
        >
          {generating ? <ActivityIndicator color={PRIMARY} size="small" /> : <Text style={styles.primaryOutlineText}>Пересоздать план</Text>}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16, paddingBottom: 32 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  title: { fontSize: 22, fontWeight: '800', color: BLACK },
  period: { fontSize: 12, color: GRAY },
  loadingText: { marginTop: 12, color: GRAY, fontSize: 14 },
  emptyTitle: { fontSize: 22, fontWeight: '800', color: BLACK, marginBottom: 8 },
  emptyText: { fontSize: 14, color: GRAY, textAlign: 'center', marginBottom: 16 },
  errorTitle: { fontSize: 22, fontWeight: '800', color: BLACK, marginBottom: 8 },
  errorText: { fontSize: 13, color: RED, textAlign: 'center', marginBottom: 12 },
  errorBanner: { backgroundColor: '#FEF2F2', color: RED, borderRadius: 12, padding: 12, marginBottom: 12, textAlign: 'center' },
  daysRow: { gap: 8, paddingBottom: 8 },
  dayChip: {
    minWidth: 52,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 14,
    backgroundColor: CARD,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    alignItems: 'center',
  },
  dayChipActive: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  dayChipShort: { fontSize: 11, fontWeight: '600', color: GRAY },
  dayChipShortActive: { color: '#FFFFFF' },
  dayChipDate: { fontSize: 17, fontWeight: '800', color: BLACK, marginTop: 2 },
  dayChipDateActive: { color: '#FFFFFF' },
  dayHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: 12 },
  dayTitle: { fontSize: 16, fontWeight: '700', color: BLACK },
  dayMeta: { fontSize: 12, color: GRAY },
  mealCard: {
    backgroundColor: CARD,
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  mealContent: { flex: 1 },
  mealMeta: { fontSize: 12, color: GRAY, marginBottom: 4 },
  mealTitle: { fontSize: 17, fontWeight: '700', color: BLACK, marginBottom: 6 },
  mealKcal: { fontSize: 14, fontWeight: '700', color: PRIMARY },
  recipeToggle: {
    marginTop: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: '#EEF8F2',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  recipeToggleOpen: { backgroundColor: '#E1F3E8' },
  recipeToggleText: { color: PRIMARY, fontSize: 13, fontWeight: '700' },
  recipeToggleArrow: { color: PRIMARY, fontSize: 11, fontWeight: '700' },
  recipeBox: {
    marginTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    paddingTop: 10,
    gap: 4,
  },
  recipeMeta: { color: PRIMARY, fontSize: 12, fontWeight: '700', marginBottom: 4 },
  recipeSectionTitle: { color: BLACK, fontSize: 13, fontWeight: '700', marginTop: 6, marginBottom: 2 },
  recipeLine: { color: GRAY, fontSize: 13, lineHeight: 18 },
  smallButton: {
    minWidth: 86,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#D1FAE5',
    alignItems: 'center',
    justifyContent: 'center',
  },
  smallButtonText: { color: PRIMARY, fontSize: 13, fontWeight: '700' },
  summaryCard: { backgroundColor: CARD, borderRadius: 16, padding: 16, marginTop: 8 },
  summaryTitle: { fontSize: 15, fontWeight: '700', color: BLACK, marginBottom: 12 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  summaryItem: { flex: 1, alignItems: 'center' },
  summaryValue: { fontSize: 18, fontWeight: '800', color: PRIMARY },
  summaryLabel: { fontSize: 11, color: GRAY, marginTop: 4 },
  primaryButton: {
    minWidth: 220,
    backgroundColor: PRIMARY,
    borderRadius: 12,
    paddingHorizontal: 18,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '700' },
  primaryOutlineButton: {
    marginTop: 14,
    borderRadius: 12,
    paddingVertical: 14,
    borderWidth: 1.5,
    borderColor: PRIMARY,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryOutlineText: { color: PRIMARY, fontSize: 15, fontWeight: '700' },
  secondaryButton: {
    marginTop: 12,
    backgroundColor: '#EAF7EF',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryButtonText: { color: PRIMARY, fontSize: 15, fontWeight: '700' },
  buttonDisabled: { opacity: 0.6 },
  emptyMealsCard: { backgroundColor: CARD, borderRadius: 14, padding: 18, alignItems: 'center' },
  emptyMealsText: { color: GRAY, fontSize: 14 },
});
