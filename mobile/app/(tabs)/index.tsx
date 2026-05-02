import { Ionicons } from '@expo/vector-icons';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { planApi, PlanMeal } from '@/api/plan';
import { useAuthStore } from '@/store/authStore';
import { usePlanStore } from '@/store/planStore';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';
const BORDER = '#D4DAD5';
const MUTED = '#F0EEE7';
const GREEN_SOFT = '#E8E4D9';
const RED = '#C8553D';

type MacroKey = 'kcal' | 'protein' | 'fat' | 'carbs';
type Totals = Record<MacroKey, number>;

const DAY_NAMES = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
const DAY_SHORT = ['ВС', 'ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ'];
const MONTH_NAMES = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];

function localIsoDate(value = new Date()) {
  const y = value.getFullYear();
  const m = String(value.getMonth() + 1).padStart(2, '0');
  const d = String(value.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function todayLabel(): string {
  const d = new Date();
  return `${DAY_NAMES[d.getDay()]}, ${d.getDate()} ${MONTH_NAMES[d.getMonth()]}`;
}

function fullDateLabel(iso?: string | null) {
  if (!iso) return '—';
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return `${DAY_NAMES[d.getDay()]}, ${d.getDate()} ${MONTH_NAMES[d.getMonth()]}`;
}

function formatDayMonth(iso?: string | null) {
  if (!iso) return '—';
  const [year, month, day] = iso.split('-');
  if (!year || !month || !day) return iso;
  return `${day}.${month}`;
}

function formatDayChip(iso?: string | null) {
  if (!iso) return { day: '—', date: '—' };
  const d = new Date(`${iso}T00:00:00`);
  return {
    day: DAY_SHORT[d.getDay()],
    date: formatDayMonth(iso),
  };
}

function minutesOfDay(time?: string | null) {
  const match = /^(\d{1,2}):(\d{2})/.exec(time ?? '');
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function isPastMeal(meal: PlanMeal) {
  const scheduled = minutesOfDay(meal.meal_time);
  if (scheduled === null) return false;
  const now = new Date();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  return nowMinutes >= scheduled + 30;
}

function emptyTotals(): Totals {
  return { kcal: 0, protein: 0, fat: 0, carbs: 0 };
}

function addTotals(a: Totals, b?: PlanMeal['kbzhu_actual']): Totals {
  return {
    kcal: a.kcal + Number(b?.kcal ?? 0),
    protein: a.protein + Number(b?.protein ?? 0),
    fat: a.fat + Number(b?.fat ?? 0),
    carbs: a.carbs + Number(b?.carbs ?? 0),
  };
}

function mealInstruction(meal: PlanMeal) {
  const name = meal.description ?? 'Блюдо';
  const lower = name.toLowerCase();
  const label = meal.container_label ? `Достать контейнер ${meal.container_label}.` : 'Достать порцию.';

  if (lower.includes('арбузный пунш')) {
    return `${label} Охладить, добавить лёд перед подачей.`;
  }
  if (lower.includes('кукси') || lower.includes('гаспачо') || lower.includes('холодн')) {
    return `${label} Не греть; перемешать и добавить свежие элементы, если они отдельно.`;
  }
  if (lower.includes('салат')) {
    return `${label} Не греть; перемешать, добавить соус или зелень перед едой.`;
  }
  if (meal.heating_instructions) {
    return `${label} ${meal.heating_instructions}`;
  }
  return `${label} Разогреть по необходимости.`;
}

function statusLabel(status: string) {
  if (status === 'eaten') return 'съедено';
  if (status === 'skipped') return 'пропущено';
  return 'запланировано';
}

function MacroBar({ label, current, total, color }: { label: string; current: number; total: number; color: string }) {
  const pct = total > 0 ? Math.min(current / total, 1) : 0;
  return (
    <View style={styles.macroRow}>
      <Text style={styles.macroLabel}>{label}</Text>
      <View style={styles.macroTrack}>
        <View style={[styles.macroFill, { width: `${pct * 100}%`, backgroundColor: color }]} />
      </View>
      <Text style={styles.macroValue}>
        {Math.round(current)}
        <Text style={styles.macroTotal}>/{Math.round(total)}</Text>
      </Text>
    </View>
  );
}

export default function HomeScreen() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const plan = usePlanStore((state) => state.plan);
  const hasFetchedCurrent = usePlanStore((state) => state.hasFetchedCurrent);
  const loading = usePlanStore((state) => state.loading);
  const error = usePlanStore((state) => state.error);
  const setMealStatus = usePlanStore((state) => state.setMealStatus);
  const [savingMealId, setSavingMealId] = useState<number | null>(null);
  const [swapMealId, setSwapMealId] = useState<number | null>(null);
  const [replacementMode, setReplacementMode] = useState<'prepared' | 'manual' | null>(null);
  const [manualText, setManualText] = useState('');
  const [manualReplacements, setManualReplacements] = useState<Record<number, string>>({});
  const [swappingMealId, setSwappingMealId] = useState<number | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const autoMarked = useRef<Set<number>>(new Set());
  const hasRedirectedToAgent = useRef(false);

  useEffect(() => {
    if (!isAuthenticated || !accessToken) return;
    void usePlanStore.getState().fetchPlan();
  }, [accessToken, isAuthenticated]);

  // First-visit redirect: new user with no plan → open agent onboarding
  useEffect(() => {
    if (hasRedirectedToAgent.current) return;
    if (hasFetchedCurrent && !plan && !loading) {
      hasRedirectedToAgent.current = true;
      router.replace('/(tabs)/agent');
    }
  }, [hasFetchedCurrent, plan, loading]);

  const today = localIsoDate();
  const days = plan?.days ?? [];
  const selectedDayDate = selectedDate ?? today;
  const selectedDay = useMemo(
    () => days.find((day) => day.date === selectedDayDate) ?? days.find((day) => day.date === today) ?? days[0] ?? null,
    [days, selectedDayDate, today],
  );
  const meals = useMemo(
    () => [...(selectedDay?.meals ?? [])].sort((a, b) => (minutesOfDay(a.meal_time) ?? 9999) - (minutesOfDay(b.meal_time) ?? 9999)),
    [selectedDay],
  );
  const weekMeals = useMemo(
    () => (plan?.days ?? []).flatMap((day) => day.meals.map((meal) => ({ ...meal, day_date: day.date }))),
    [plan],
  );

  const consumed = useMemo(
    () => meals.filter((meal) => meal.status === 'eaten').reduce((acc, meal) => addTotals(acc, meal.kbzhu_actual), emptyTotals()),
    [meals],
  );
  const targets = plan?.daily_targets ?? emptyTotals();

  const updateStatus = async (meal: PlanMeal, status: 'planned' | 'eaten' | 'skipped') => {
    if (savingMealId) return;
    setSavingMealId(meal.id);
    const previous = meal.status;
    setMealStatus(meal.id, status);
    try {
      await planApi.updateMealStatus(meal.id, status);
    } catch {
      setMealStatus(meal.id, previous);
    } finally {
      setSavingMealId(null);
    }
  };

  const swapPreparedMeal = async (meal: PlanMeal, targetMealId: number) => {
    if (swappingMealId) return;
    setSwappingMealId(meal.id);
    try {
      await planApi.swapPreparedMeal(meal.id, targetMealId);
      await usePlanStore.getState().fetchPlan();
      setSwapMealId(null);
    } finally {
      setSwappingMealId(null);
    }
  };

  const saveManualReplacement = async (meal: PlanMeal) => {
    const value = manualText.trim();
    if (!value || swappingMealId) return;
    setSwappingMealId(meal.id);
    try {
      await planApi.manualReplacement(meal.id, value);
      setManualReplacements((prev) => ({ ...prev, [meal.id]: value }));
      await usePlanStore.getState().fetchPlan();
      setSwapMealId(null);
      setReplacementMode(null);
      setManualText('');
    } finally {
      setSwappingMealId(null);
    }
  };

  useEffect(() => {
    const todayMeals = days.find((day) => day.date === today)?.meals ?? [];
    if (!todayMeals.length || savingMealId) return;
    for (const meal of todayMeals) {
      if (meal.status === 'planned' && isPastMeal(meal) && !autoMarked.current.has(meal.id)) {
        autoMarked.current.add(meal.id);
        void updateStatus(meal, 'eaten');
        break;
      }
    }
  }, [days, today, savingMealId]);

  const nextMealId = meals.find((meal) => meal.status === 'planned')?.id ?? null;

  if (loading && !plan) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={PRIMARY} />
          <Text style={styles.loadingText}>Загружаем сегодняшний день...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!plan) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.content}>
          <Text style={styles.title}>Сегодня</Text>
          <View style={styles.noPlanCard}>
            <View style={styles.noPlanIconWrap}>
              <Ionicons name="calendar-outline" size={32} color={PRIMARY} />
            </View>
            <Text style={styles.noPlanTitle}>Плана питания нет</Text>
            <Text style={styles.noPlanHint}>Создай меню на следующую неделю — и здесь появятся приёмы пищи, контейнеры и КБЖУ на каждый день.</Text>
            <TouchableOpacity
              style={styles.noPlanBtn}
              onPress={() => router.push('/(tabs)/plan')}
              activeOpacity={0.85}
            >
              <Text style={styles.noPlanBtnText}>Создать план</Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>{selectedDay?.date === today ? 'Сегодня' : 'План дня'}</Text>
            <Text style={styles.date}>{selectedDay?.date === today ? todayLabel() : fullDateLabel(selectedDay?.date)}</Text>
          </View>
          <View style={styles.kcalPill}>
            <Text style={styles.kcalPillValue}>{Math.round(consumed.kcal)}</Text>
            <Text style={styles.kcalPillLabel}>из {Math.round(targets.kcal)} ккал</Text>
          </View>
        </View>

        {days.length > 0 ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.dayTabs}>
            {days.map((day) => {
              const label = formatDayChip(day.date);
              const active = selectedDay?.date === day.date;
              return (
                <TouchableOpacity
                  key={day.id}
                  style={[styles.dayTab, active && styles.dayTabActive]}
                  onPress={() => {
                    setSelectedDate(day.date);
                    setSwapMealId(null);
                    setReplacementMode(null);
                  }}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.dayTabDay, active && styles.dayTabTextActive]}>{label.day}</Text>
                  <Text style={[styles.dayTabDate, active && styles.dayTabTextActive]}>{label.date}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        ) : null}

        <View style={styles.summary}>
          <MacroBar label="ккал" current={consumed.kcal} total={targets.kcal} color={PRIMARY} />
          <MacroBar label="Б" current={consumed.protein} total={targets.protein} color="#4A5C4D" />
          <MacroBar label="Ж" current={consumed.fat} total={targets.fat} color="#C9A14B" />
          <MacroBar label="У" current={consumed.carbs} total={targets.carbs} color="#C8553D" />
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Приёмы пищи</Text>
          <Text style={styles.sectionMeta}>{meals.length} · {formatDayMonth(selectedDay?.date)}</Text>
        </View>

        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        {!plan ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>Плана пока нет</Text>
            <Text style={styles.emptyText}>Создайте меню на вкладке «План», и здесь появится сегодняшний день.</Text>
          </View>
        ) : meals.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>На сегодня нет приёмов пищи</Text>
            <Text style={styles.emptyText}>Проверьте даты текущего плана на вкладке «План».</Text>
          </View>
        ) : (
          meals.map((meal) => {
            const isNext = meal.id === nextMealId;
            const isSaving = savingMealId === meal.id;
            const isSwapping = swappingMealId === meal.id;
            const kcal = Math.round(Number(meal.kbzhu_actual?.kcal ?? 0));
            const displayTitle = manualReplacements[meal.id] ? `Вручную: ${manualReplacements[meal.id]}` : (meal.description ?? 'Блюдо без названия');
            const preparedOptions = weekMeals.filter((candidate) => (
              candidate.id !== meal.id
              && candidate.status !== 'eaten'
              && Boolean(candidate.container_id)
              && String(candidate.day_date) >= today
            ));
            return (
              <View key={meal.id} style={[styles.mealCard, isNext && styles.mealCardNext, meal.status === 'skipped' && styles.mealCardSkipped]}>
                <View style={styles.mealTop}>
                  <View style={styles.timeBlock}>
                    <Text style={styles.timeText}>{meal.meal_time ?? '--:--'}</Text>
                    <Text style={styles.mealName}>{meal.meal_name ?? meal.meal_type}</Text>
                  </View>
                  <View style={[styles.statusPill, meal.status === 'eaten' && styles.statusEaten, meal.status === 'skipped' && styles.statusSkipped]}>
                    <Text style={[styles.statusText, meal.status === 'eaten' && styles.statusTextEaten, meal.status === 'skipped' && styles.statusTextSkipped]}>
                      {statusLabel(meal.status)}
                    </Text>
                  </View>
                </View>

                <View style={styles.mealBody}>
                  <View style={styles.containerBadge}>
                    <Text style={styles.containerBadgeText}>{meal.container_label ?? '—'}</Text>
                  </View>
                  <View style={styles.mealInfo}>
                    <Text style={styles.mealTitle}>{displayTitle}</Text>
                    <Text style={styles.instruction}>{mealInstruction(meal)}</Text>
                  </View>
                  <View style={styles.kcalBox}>
                    <Text style={styles.kcalValue}>{kcal}</Text>
                    <Text style={styles.kcalLabel}>ккал</Text>
                  </View>
                </View>

                <View style={styles.actions}>
                  <TouchableOpacity
                    style={[styles.actionButton, meal.status === 'eaten' && styles.actionButtonActive]}
                    onPress={() => updateStatus(meal, 'eaten')}
                    disabled={isSaving}
                    activeOpacity={0.8}
                  >
                    <Ionicons name="checkmark" size={16} color={meal.status === 'eaten' ? '#FFFFFF' : PRIMARY} />
                    <Text style={[styles.actionText, meal.status === 'eaten' && styles.actionTextActive]}>Съел</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.actionButton, styles.skipButton, meal.status === 'skipped' && styles.skipButtonActive]}
                    onPress={() => updateStatus(meal, 'skipped')}
                    disabled={isSaving}
                    activeOpacity={0.8}
                  >
                    <Ionicons name="close" size={16} color={meal.status === 'skipped' ? '#FFFFFF' : RED} />
                    <Text style={[styles.actionText, styles.skipText, meal.status === 'skipped' && styles.actionTextActive]}>Не съел</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.actionButton, styles.replaceButton]}
                    onPress={() => {
                      setSwapMealId(swapMealId === meal.id ? null : meal.id);
                      setReplacementMode(null);
                      setManualText('');
                    }}
                    disabled={isSaving || meal.status === 'eaten'}
                    activeOpacity={0.8}
                  >
                    <Ionicons name="swap-horizontal" size={16} color={PRIMARY} />
                    <Text style={[styles.actionText, styles.replaceText]}>Замена</Text>
                  </TouchableOpacity>
                </View>

                {swapMealId === meal.id && meal.status !== 'eaten' ? (
                  <View style={styles.swapBlock}>
                    <View style={styles.replaceChoiceRow}>
                      <TouchableOpacity
                        style={[styles.replaceChoice, replacementMode === 'prepared' && styles.replaceChoiceActive]}
                        onPress={() => setReplacementMode('prepared')}
                        activeOpacity={0.8}
                      >
                        <Text style={[styles.replaceChoiceText, replacementMode === 'prepared' && styles.replaceChoiceTextActive]}>На готовое</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.replaceChoice, replacementMode === 'manual' && styles.replaceChoiceActive]}
                        onPress={() => setReplacementMode('manual')}
                        activeOpacity={0.8}
                      >
                        <Text style={[styles.replaceChoiceText, replacementMode === 'manual' && styles.replaceChoiceTextActive]}>Вручную</Text>
                      </TouchableOpacity>
                    </View>
                    {replacementMode === 'prepared' ? (
                      <View style={styles.swapOptions}>
                        {preparedOptions.length === 0 ? (
                          <Text style={styles.swapEmpty}>Нет будущих готовых блюд для замены.</Text>
                        ) : preparedOptions.slice(0, 8).map((candidate) => (
                          <TouchableOpacity
                            key={`swap-${meal.id}-${candidate.id}`}
                            style={styles.swapOption}
                            onPress={() => swapPreparedMeal(meal, candidate.id)}
                            disabled={isSwapping}
                            activeOpacity={0.8}
                          >
                            <Text style={styles.swapOptionText}>
                              {candidate.container_label ?? '—'} · {candidate.description ?? 'Блюдо'}
                            </Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    ) : null}
                    {replacementMode === 'manual' ? (
                      <View style={styles.manualBox}>
                        <TextInput
                          style={styles.manualInput}
                          value={manualText}
                          onChangeText={setManualText}
                          placeholder="Например: шаурма"
                          placeholderTextColor={GRAY}
                        />
                        <TouchableOpacity
                          style={styles.manualSave}
                          onPress={() => saveManualReplacement(meal)}
                          disabled={isSwapping || !manualText.trim()}
                          activeOpacity={0.8}
                        >
                          <Text style={styles.manualSaveText}>Записать</Text>
                        </TouchableOpacity>
                      </View>
                    ) : null}
                  </View>
                ) : null}
              </View>
            );
          })
        )}

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16, paddingBottom: 28 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  loadingText: { marginTop: 10, color: GRAY, fontSize: 14 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 },
  title: { fontSize: 30, fontWeight: '800', color: BLACK , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.6},
  date: { marginTop: 2, fontSize: 14, color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  kcalPill: { backgroundColor: PRIMARY, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8, alignItems: 'flex-end' },
  kcalPillValue: { color: '#FFFFFF', fontSize: 20, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  kcalPillLabel: { color: 'rgba(255,255,255,0.82)', fontSize: 11 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  dayTabs: { gap: 8, paddingBottom: 10 },
  dayTab: { minWidth: 58, borderRadius: 8, borderWidth: 1, borderColor: BORDER, backgroundColor: CARD, paddingVertical: 8, alignItems: 'center' },
  dayTabActive: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  dayTabDay: { color: GRAY, fontSize: 11, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  dayTabDate: { color: BLACK, fontSize: 13, fontWeight: '900', marginTop: 2 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  dayTabTextActive: { color: '#FFFFFF' },
  summary: { backgroundColor: CARD, borderRadius: 8, borderWidth: 1, borderColor: BORDER, padding: 14, marginBottom: 16 },
  macroRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginVertical: 4 },
  macroLabel: { width: 32, fontSize: 12, fontWeight: '700', color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  macroTrack: { flex: 1, height: 8, borderRadius: 4, backgroundColor: MUTED, overflow: 'hidden' },
  macroFill: { height: 8, borderRadius: 4 },
  macroValue: { width: 68, textAlign: 'right', fontSize: 12, fontWeight: '800', color: BLACK , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  macroTotal: { color: GRAY, fontWeight: '500' },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  sectionTitle: { fontSize: 17, fontWeight: '800', color: BLACK , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.34},
  sectionMeta: { fontSize: 13, color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  errorText: { color: RED, fontSize: 13, marginBottom: 10 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  emptyCard: { backgroundColor: CARD, borderRadius: 8, borderWidth: 1, borderColor: BORDER, padding: 18 },
  emptyTitle: { fontSize: 16, fontWeight: '800', color: BLACK, marginBottom: 4 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.32},
  emptyText: { fontSize: 13, color: GRAY, lineHeight: 18 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  noPlanCard: { backgroundColor: CARD, borderRadius: 16, borderWidth: 1, borderColor: BORDER, padding: 24, alignItems: 'center', marginTop: 8 },
  noPlanIconWrap: { width: 64, height: 64, borderRadius: 32, backgroundColor: '#E8E4D9', alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  noPlanTitle: { fontSize: 18, fontWeight: '800', color: BLACK, marginBottom: 8, textAlign: 'center', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.36 },
  noPlanHint: { fontSize: 14, color: GRAY, lineHeight: 20, textAlign: 'center', marginBottom: 20, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  noPlanBtn: { backgroundColor: PRIMARY, borderRadius: 12, paddingHorizontal: 24, paddingVertical: 13 },
  noPlanBtnText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  mealCard: { backgroundColor: CARD, borderRadius: 8, borderWidth: 1, borderColor: BORDER, padding: 14, marginBottom: 10 },
  mealCardNext: { borderColor: PRIMARY },
  mealCardSkipped: { opacity: 0.78 },
  mealTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 },
  timeBlock: { flexShrink: 1 },
  timeText: { fontSize: 15, fontWeight: '800', color: BLACK , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  mealName: { marginTop: 1, fontSize: 12, color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  statusPill: { backgroundColor: MUTED, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  statusEaten: { backgroundColor: GREEN_SOFT },
  statusSkipped: { backgroundColor: '#FCEAE6' },
  statusText: { fontSize: 11, fontWeight: '700', color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  statusTextEaten: { color: PRIMARY },
  statusTextSkipped: { color: RED },
  mealBody: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  containerBadge: { width: 42, height: 42, borderRadius: 8, backgroundColor: GREEN_SOFT, borderWidth: 1, borderColor: '#9AE6B4', alignItems: 'center', justifyContent: 'center' },
  containerBadgeText: { color: PRIMARY, fontSize: 14, fontWeight: '900' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  mealInfo: { flex: 1, minWidth: 0 },
  mealTitle: { color: BLACK, fontSize: 15, fontWeight: '800', lineHeight: 19 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3},
  instruction: { color: GRAY, fontSize: 12, lineHeight: 17, marginTop: 4 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  kcalBox: { width: 48, alignItems: 'flex-end' },
  kcalValue: { fontSize: 17, fontWeight: '800', color: BLACK , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  kcalLabel: { fontSize: 10, color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  actions: { flexDirection: 'row', gap: 8, marginTop: 12 },
  actionButton: { flex: 1, height: 40, borderRadius: 8, borderWidth: 1, borderColor: PRIMARY, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, backgroundColor: '#FAFAF7' },
  actionButtonActive: { backgroundColor: PRIMARY },
  skipButton: { borderColor: RED },
  skipButtonActive: { backgroundColor: RED },
  replaceButton: { borderColor: PRIMARY, backgroundColor: '#F0EEE7' },
  actionText: { color: PRIMARY, fontSize: 14, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  skipText: { color: RED },
  replaceText: { color: PRIMARY },
  actionTextActive: { color: '#FFFFFF' },
  swapBlock: { marginTop: 10 },
  replaceChoiceRow: { flexDirection: 'row', gap: 8 },
  replaceChoice: { flex: 1, borderRadius: 8, borderWidth: 1, borderColor: BORDER, backgroundColor: '#FAFAF7', paddingVertical: 9, alignItems: 'center' },
  replaceChoiceActive: { borderColor: PRIMARY, backgroundColor: '#E8E4D9' },
  replaceChoiceText: { color: GRAY, fontSize: 13, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  replaceChoiceTextActive: { color: PRIMARY },
  swapOptions: { marginTop: 8, gap: 6 },
  swapEmpty: { color: GRAY, fontSize: 12, lineHeight: 17 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  swapOption: { borderRadius: 8, borderWidth: 1, borderColor: BORDER, backgroundColor: '#FAFAF7', paddingHorizontal: 10, paddingVertical: 8 },
  swapOptionText: { color: BLACK, fontSize: 12, fontWeight: '700', lineHeight: 16 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  manualBox: { marginTop: 8, flexDirection: 'row', gap: 8 },
  manualInput: { flex: 1, minHeight: 40, borderRadius: 8, borderWidth: 1, borderColor: BORDER, backgroundColor: '#FAFAF7', paddingHorizontal: 10, color: BLACK, fontSize: 13 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  manualSave: { minWidth: 86, borderRadius: 8, backgroundColor: PRIMARY, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12 },
  manualSaveText: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  weekCard: { marginTop: 10, backgroundColor: CARD, borderRadius: 8, borderWidth: 1, borderColor: BORDER, padding: 14 },
  weekTitle: { color: BLACK, fontSize: 16, fontWeight: '900', marginBottom: 10 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.32},
  weekDay: { borderTopWidth: 1, borderTopColor: BORDER, paddingTop: 8, marginTop: 8, flexDirection: 'row', gap: 10 },
  weekDayDate: { width: 44, color: PRIMARY, fontSize: 12, fontWeight: '900' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  weekMeals: { flex: 1, gap: 3 },
  weekMealLine: { color: GRAY, fontSize: 12, lineHeight: 16 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
});
