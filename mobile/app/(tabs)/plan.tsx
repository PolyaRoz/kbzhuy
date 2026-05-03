import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { planApi, MealPlanResponse } from '../../src/api/plan';
import { cookingApi } from '../../src/api/cooking';
import { useAuthStore } from '../../src/store/authStore';
import { usePlanStore } from '../../src/store/planStore';
import { useShoppingStore } from '../../src/store/shoppingStore';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';
const RED = '#C8553D';

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
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return '—';
  return `${d.getDate()} ${MONTH_SHORT[d.getMonth()]}`;
}

function formatDayShort(iso?: string | null) {
  if (!iso) return '—';
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return '—';
  return DAY_SHORT[d.getDay()];
}

function formatDayFull(iso?: string | null) {
  if (!iso) return '—';
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return '—';
  return DAY_FULL[d.getDay()];
}

function localIsoDate(value = new Date()) {
  const y = value.getFullYear();
  const m = String(value.getMonth() + 1).padStart(2, '0');
  const d = String(value.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

// Coming Monday — base for plan weeks.
function nextMondayIso() {
  const d = new Date();
  const day = d.getDay();
  const daysUntil = day === 0 ? 1 : 8 - day;
  d.setDate(d.getDate() + daysUntil);
  return localIsoDate(d);
}

function plusDaysIso(iso: string, days: number) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return localIsoDate(d);
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

  const [plan, setPlan] = useState<MealPlanResponse | null>(null);
  const [hasFetchedCurrent, setHasFetchedCurrent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [replacingMealId, setReplacingMealId] = useState<number | null>(null);
  const [rebuildingDayId, setRebuildingDayId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selectedIdx, setSelectedIdx] = useState(0);
  // weekOffset: 0 = next Monday, 1 = Monday +7 (week after next)
  const [weekOffset, setWeekOffset] = useState(0);

  const baseMonday = nextMondayIso();
  const periodStart = weekOffset === 0 ? baseMonday : plusDaysIso(baseMonday, 7 * weekOffset);
  const periodEnd = plusDaysIso(periodStart, 6);

  const weekLabel = weekOffset === 0 ? 'Следующая неделя' : `Через ${weekOffset + 1} недели`;

  const fetchPlanningPlan = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await planApi.getByPeriod(periodStart);
      setPlan(data);
      setHasFetchedCurrent(true);
    } catch (e: any) {
      if (e?.response?.status === 404) {
        setPlan(null);
        setHasFetchedCurrent(true);
      } else {
        setError(e?.response?.data?.detail ?? e?.message ?? 'Ошибка загрузки плана');
        setHasFetchedCurrent(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const generatePlanningPlan = async () => {
    setGenerating(true);
    setError(null);
    try {
      await planApi.generate({ period_start: periodStart, period_end: periodEnd, use_ai: false });
      // Generate cooking plan immediately after meal plan
      try { await cookingApi.generatePlan(); } catch (_) { /* ignore if already exists */ }
      await fetchPlanningPlan();
      // Sync all global stores so other tabs update immediately without navigation
      await usePlanStore.getState().fetchPlan();
      void useShoppingStore.getState().fetchList();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? 'Ошибка генерации плана');
    } finally {
      setGenerating(false);
    }
  };

  const replaceMeal = async (mealId: number) => {
    setReplacingMealId(mealId);
    setError(null);
    try {
      await planApi.replaceMeal(mealId);
      await fetchPlanningPlan();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? 'Не удалось заменить блюдо');
    } finally {
      setReplacingMealId(null);
    }
  };

  const rebuildDay = async (dayId: number) => {
    setRebuildingDayId(dayId);
    setError(null);
    try {
      await planApi.rebuildDay(dayId);
      await fetchPlanningPlan();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? 'Не удалось пересобрать день');
    } finally {
      setRebuildingDayId(null);
    }
  };

  // Reset when auth changes
  useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      setSelectedIdx(0);
      setPlan(null);
      setHasFetchedCurrent(false);
      setWeekOffset(0);
      return;
    }
    setSelectedIdx(0);
  }, [accessToken, isAuthenticated]);

  // Reset + refetch when week offset changes
  useEffect(() => {
    setPlan(null);
    setHasFetchedCurrent(false);
    setSelectedIdx(0);
  }, [weekOffset]);

  useEffect(() => {
    if (!isAuthenticated || !accessToken) return;
    if (hasFetchedCurrent || loading) return;
    void fetchPlanningPlan();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, hasFetchedCurrent, isAuthenticated, loading]);

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

  if (!plan && hasFetchedCurrent) {
    return (
      <SafeAreaView style={styles.safe}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {/* Header with week navigation */}
          <View style={styles.header}>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>{weekLabel}</Text>
              <Text style={styles.headerHint}>Меню для подготовки еды; замены обновляют покупки</Text>
            </View>
            <View style={styles.headerNav}>
              {weekOffset > 0 ? (
                <TouchableOpacity
                  style={styles.navChip}
                  onPress={() => setWeekOffset((v) => Math.max(0, v - 1))}
                  activeOpacity={0.8}
                >
                  <Text style={styles.navChipText}>← Назад</Text>
                </TouchableOpacity>
              ) : null}
              <Text style={styles.period}>{formatShortDate(periodStart)} — {formatShortDate(periodEnd)}</Text>
              <TouchableOpacity
                style={styles.navChipNext}
                onPress={() => setWeekOffset((v) => v + 1)}
                activeOpacity={0.8}
              >
                <Text style={styles.navChipNextText}>Сл. план →</Text>
              </TouchableOpacity>
            </View>
          </View>

          {error ? <Text style={styles.errorBanner}>{error}</Text> : null}

          <View style={styles.createPlanCard}>
            <Text style={styles.createPlanTitle}>Нет плана на эту неделю</Text>
            <Text style={styles.createPlanHint}>
              {formatShortDate(periodStart)} — {formatShortDate(periodEnd)}
              {'\n'}Создайте план — меню сформируется по вашему профилю питания.
            </Text>
            <TouchableOpacity
              style={[styles.primaryButton, generating && styles.buttonDisabled]}
              onPress={() => void generatePlanningPlan()}
              disabled={generating}
              activeOpacity={0.8}
            >
              {generating
                ? <ActivityIndicator color="#FFFFFF" />
                : <Text style={styles.primaryButtonText}>Создать план</Text>}
            </TouchableOpacity>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  const days = Array.isArray(plan?.days) ? plan!.days : [];
  const safeSelectedIdx = days.length === 0 ? 0 : Math.min(selectedIdx, days.length - 1);
  const selectedDay = days[safeSelectedIdx];
  const meals = Array.isArray(selectedDay?.meals) ? selectedDay.meals : [];
  const totals = totalsFromMeals(meals);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Header with week navigation */}
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>{weekLabel}</Text>
            <Text style={styles.headerHint}>Меню для подготовки еды; замены обновляют покупки</Text>
          </View>
          <View style={styles.headerNav}>
            {weekOffset > 0 ? (
              <TouchableOpacity
                style={styles.navChip}
                onPress={() => setWeekOffset((v) => Math.max(0, v - 1))}
                activeOpacity={0.8}
              >
                <Text style={styles.navChipText}>← Назад</Text>
              </TouchableOpacity>
            ) : null}
            <Text style={styles.period}>
              {formatShortDate(plan?.period_start ?? periodStart)} — {formatShortDate(plan?.period_end ?? periodEnd)}
            </Text>
            <TouchableOpacity
              style={styles.navChipNext}
              onPress={() => setWeekOffset((v) => v + 1)}
              activeOpacity={0.8}
            >
              <Text style={styles.navChipNextText}>Сл. план →</Text>
            </TouchableOpacity>
          </View>
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
              <Text style={[styles.dayChipDate, idx === safeSelectedIdx && styles.dayChipDateActive]}>{new Date(`${day.date}T00:00:00`).getDate()}</Text>
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
                <Text style={styles.mealKcal}>
                  {meal.recipe_details?.serving_grams ? `${Math.round(Number(meal.recipe_details.serving_grams))} г · ` : ''}
                  {Math.round(Number(meal?.kbzhu_actual?.kcal ?? 0))} ккал · Б {Math.round(Number(meal?.kbzhu_actual?.protein ?? 0))} г · Ж {Math.round(Number(meal?.kbzhu_actual?.fat ?? 0))} г · У {Math.round(Number(meal?.kbzhu_actual?.carbs ?? 0))} г
                </Text>
              </View>

              <TouchableOpacity
                style={[styles.smallButton, replacingMealId === meal.id && styles.buttonDisabled]}
                onPress={() => void replaceMeal(meal.id)}
                disabled={Boolean(replacingMealId) || Boolean(rebuildingDayId) || generating}
                activeOpacity={0.8}
              >
                {replacingMealId === meal.id
                  ? <ActivityIndicator color={PRIMARY} size="small" />
                  : <Text style={styles.smallButtonText}>Заменить</Text>}
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
            onPress={() => void rebuildDay(selectedDay.id)}
            disabled={Boolean(replacingMealId) || Boolean(rebuildingDayId) || generating}
            activeOpacity={0.8}
          >
            {rebuildingDayId === selectedDay.id
              ? <ActivityIndicator color={PRIMARY} size="small" />
              : <Text style={styles.secondaryButtonText}>Пересобрать день</Text>}
          </TouchableOpacity>
        ) : null}

        <TouchableOpacity
          style={[styles.primaryOutlineButton, generating && styles.buttonDisabled]}
          onPress={() => void generatePlanningPlan()}
          disabled={generating}
          activeOpacity={0.8}
        >
          {generating
            ? <ActivityIndicator color={PRIMARY} size="small" />
            : <Text style={styles.primaryOutlineText}>Пересоздать план</Text>}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16, paddingBottom: 32 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14, gap: 12 },
  title: { fontSize: 22, fontWeight: '800', color: BLACK, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.44 },
  headerHint: { marginTop: 3, fontSize: 12, color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  headerNav: { alignItems: 'flex-end', gap: 6 },
  period: { fontSize: 12, color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  navChip: {
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
    backgroundColor: '#E8E4D9',
    borderWidth: 1,
    borderColor: '#D4DAD5',
  },
  navChipText: { fontSize: 12, fontWeight: '700', color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  navChipNext: {
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
    backgroundColor: PRIMARY,
  },
  navChipNextText: { fontSize: 12, fontWeight: '700', color: '#FFFFFF', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  loadingText: { marginTop: 12, color: GRAY, fontSize: 14, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  emptyTitle: { fontSize: 22, fontWeight: '800', color: BLACK, marginBottom: 8, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.44 },
  emptyText: { fontSize: 14, color: GRAY, textAlign: 'center', marginBottom: 16, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  errorTitle: { fontSize: 22, fontWeight: '800', color: BLACK, marginBottom: 8, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.44 },
  errorText: { fontSize: 13, color: RED, textAlign: 'center', marginBottom: 12, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  errorBanner: { backgroundColor: '#FEF2F2', color: RED, borderRadius: 12, padding: 12, marginBottom: 12, textAlign: 'center' },
  daysRow: { gap: 8, paddingBottom: 8 },
  dayChip: {
    minWidth: 52,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 14,
    backgroundColor: CARD,
    borderWidth: 1,
    borderColor: '#D4DAD5',
    alignItems: 'center',
  },
  dayChipActive: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  dayChipShort: { fontSize: 11, fontWeight: '600', color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  dayChipShortActive: { color: '#FFFFFF' },
  dayChipDate: { fontSize: 17, fontWeight: '800', color: BLACK, marginTop: 2, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  dayChipDateActive: { color: '#FFFFFF' },
  dayHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: 12 },
  dayTitle: { fontSize: 16, fontWeight: '700', color: BLACK, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.32 },
  dayMeta: { fontSize: 12, color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
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
  mealMeta: { fontSize: 12, color: GRAY, marginBottom: 4, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  mealTitle: { fontSize: 17, fontWeight: '700', color: BLACK, marginBottom: 6, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.34 },
  mealKcal: { fontSize: 14, fontWeight: '700', color: PRIMARY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
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
  recipeToggleText: { color: PRIMARY, fontSize: 13, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  recipeToggleArrow: { color: PRIMARY, fontSize: 11, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  recipeBox: { marginTop: 10, borderTopWidth: 1, borderTopColor: '#D4DAD5', paddingTop: 10, gap: 4 },
  recipeMeta: { color: PRIMARY, fontSize: 12, fontWeight: '700', marginBottom: 4, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  recipeSectionTitle: { color: BLACK, fontSize: 13, fontWeight: '700', marginTop: 6, marginBottom: 2, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.26 },
  recipeLine: { color: GRAY, fontSize: 13, lineHeight: 18, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
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
  smallButtonText: { color: PRIMARY, fontSize: 13, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  summaryCard: { backgroundColor: CARD, borderRadius: 16, padding: 16, marginTop: 8 },
  summaryTitle: { fontSize: 15, fontWeight: '700', color: BLACK, marginBottom: 12, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  summaryItem: { flex: 1, alignItems: 'center' },
  summaryValue: { fontSize: 18, fontWeight: '800', color: PRIMARY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  summaryLabel: { fontSize: 11, color: GRAY, marginTop: 4, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  primaryButton: {
    minWidth: 220,
    backgroundColor: PRIMARY,
    borderRadius: 12,
    paddingHorizontal: 18,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  primaryOutlineButton: {
    marginTop: 14,
    borderRadius: 12,
    paddingVertical: 14,
    borderWidth: 1.5,
    borderColor: PRIMARY,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryOutlineText: { color: PRIMARY, fontSize: 15, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  secondaryButton: {
    marginTop: 12,
    backgroundColor: '#EAF7EF',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryButtonText: { color: PRIMARY, fontSize: 15, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  buttonDisabled: { opacity: 0.6 },
  emptyMealsCard: { backgroundColor: CARD, borderRadius: 14, padding: 18, alignItems: 'center' },
  emptyMealsText: { color: GRAY, fontSize: 14, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  createPlanCard: {
    backgroundColor: CARD,
    borderRadius: 16,
    padding: 28,
    alignItems: 'center',
    marginTop: 8,
    borderWidth: 1,
    borderColor: '#D4DAD5',
  },
  createPlanTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: BLACK,
    marginBottom: 8,
    textAlign: 'center',
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
    letterSpacing: -0.36,
  },
  createPlanHint: {
    fontSize: 14,
    color: GRAY,
    lineHeight: 20,
    textAlign: 'center',
    marginBottom: 24,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
});
