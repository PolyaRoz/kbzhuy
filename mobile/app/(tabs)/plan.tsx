import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { usePlanStore } from '../../src/store/planStore';

const PRIMARY = '#1A7340';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';
const RED = '#DC2626';

const MEAL_LABEL: Record<string, string> = {
  breakfast: 'Завтрак',
  lunch: 'Обед',
  snack: 'Перекус',
  dinner: 'Ужин',
};

const MEAL_EMOJI: Record<string, string> = {
  breakfast: '🌅',
  lunch: '☀️',
  snack: '🍎',
  dinner: '🌙',
};

const DAY_SHORT = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
const DAY_FULL = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];

function formatDate(iso: string) {
  const d = new Date(iso);
  return `${d.getDate()} ${['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек'][d.getMonth()]}`;
}

function dayShort(iso: string) { return DAY_SHORT[new Date(iso).getDay()]; }
function dayFull(iso: string)  { return DAY_FULL[new Date(iso).getDay()]; }

// ─── Empty state ────────────────────────────────────────────────────────────

function EmptyPlan({ onGenerate, loading }: { onGenerate: (notes?: string) => void; loading: boolean }) {
  const [notes, setNotes] = useState('');

  return (
    <View style={ep.container}>
      <Text style={ep.icon}>📅</Text>
      <Text style={ep.title}>Плана пока нет</Text>
      <Text style={ep.sub}>
        Создайте план питания на неделю — мы учтём профиль, цель, ограничения, бюджет и ваши вводные
      </Text>
      <TextInput
        style={ep.input}
        value={notes}
        onChangeText={setNotes}
        placeholder="Вводные: без рыбы, готовить 2 раза, больше завтраков без плиты..."
        placeholderTextColor={GRAY}
        multiline
        maxLength={500}
      />
      <TouchableOpacity style={[ep.btn, loading && ep.btnDisabled]} onPress={() => onGenerate(notes)} disabled={loading} activeOpacity={0.8}>
        {loading
          ? <ActivityIndicator color="#FFF" />
          : <Text style={ep.btnText}>Создать план на неделю</Text>
        }
      </TouchableOpacity>
    </View>
  );
}

const ep = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  icon: { fontSize: 64, marginBottom: 16 },
  title: { fontSize: 22, fontWeight: '800', color: BLACK, marginBottom: 8, letterSpacing: -0.3 },
  sub: { fontSize: 14, color: GRAY, textAlign: 'center', lineHeight: 20, marginBottom: 32 },
  input: {
    width: '100%',
    minHeight: 92,
    backgroundColor: CARD,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#D1FAE5',
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 14,
    color: BLACK,
    fontSize: 14,
    textAlignVertical: 'top',
  },
  btn: { backgroundColor: PRIMARY, borderRadius: 14, paddingVertical: 16, paddingHorizontal: 32, alignItems: 'center', width: '100%' },
  btnDisabled: { opacity: 0.6 },
  btnText: { color: '#FFF', fontSize: 16, fontWeight: '700' },
});

// ─── Main screen ─────────────────────────────────────────────────────────────

export default function PlanScreen() {
  const { plan, loading, generating, replacingMealId, rebuildingDayId, error, fetchPlan, generate, replaceMeal, rebuildDay } = usePlanStore();
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [expandedMealId, setExpandedMealId] = useState<number | null>(null);
  const initialPlanId = useRef<number | null>(null);

  useEffect(() => {
    fetchPlan();
  }, []);

  // Set selected day to today if plan covers today
  useEffect(() => {
    if (!plan) return;
    if (initialPlanId.current === plan.id) return;
    initialPlanId.current = plan.id;
    const todayISO = new Date().toISOString().slice(0, 10);
    const idx = plan.days.findIndex((d) => d.date === todayISO);
    if (idx >= 0) setSelectedIdx(idx);
  }, [plan]);

  if (loading) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.center}><ActivityIndicator size="large" color={PRIMARY} /></View>
      </SafeAreaView>
    );
  }

  if (!plan) {
    return (
      <SafeAreaView style={s.safe}>
        {error ? <Text style={s.errorBanner}>{error}</Text> : null}
        <EmptyPlan onGenerate={generate} loading={generating} />
      </SafeAreaView>
    );
  }

  const selectedDay = plan.days[selectedIdx];
  const targets = plan.daily_targets;
  const dayTotals = selectedDay.meals.reduce(
    (acc, meal) => {
      if (!meal.kbzhu_actual) return acc;
      return {
        kcal: acc.kcal + meal.kbzhu_actual.kcal,
        protein: acc.protein + meal.kbzhu_actual.protein,
        fat: acc.fat + meal.kbzhu_actual.fat,
        carbs: acc.carbs + meal.kbzhu_actual.carbs,
      };
    },
    { kcal: 0, protein: 0, fat: 0, carbs: 0 },
  );

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={s.header}>
          <Text style={s.title}>План на неделю</Text>
          <Text style={s.period}>{formatDate(plan.period_start)} — {formatDate(plan.period_end)}</Text>
        </View>

        {/* Week chips */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.weekScroll} contentContainerStyle={s.weekRow}>
          {plan.days.map((day, idx) => (
            <TouchableOpacity
              key={day.id}
              style={[s.dayChip, selectedIdx === idx && s.dayChipActive]}
              onPress={() => setSelectedIdx(idx)}
              activeOpacity={0.7}
            >
              <Text style={[s.dayChipShort, selectedIdx === idx && s.dayChipShortActive]}>{dayShort(day.date)}</Text>
              <Text style={[s.dayChipDate, selectedIdx === idx && s.dayChipDateActive]}>{new Date(day.date).getDate()}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Day header */}
        <View style={s.dayHeader}>
          <Text style={s.dayName}>{dayFull(selectedDay.date)}, {formatDate(selectedDay.date)}</Text>
          <Text style={s.dayMealCount}>{selectedDay.meals.length} приёма</Text>
        </View>

        {/* Meals */}
        {selectedDay.meals.length === 0 ? (
          <View style={s.noMeals}>
            <Text style={s.noMealsText}>Нет приёмов пищи на этот день</Text>
          </View>
        ) : (
          selectedDay.meals.map((meal) => {
            const isExpanded = expandedMealId === meal.id;
            const recipe = meal.recipe_details;
            return (
            <View key={meal.id} style={[s.mealCard, meal.status === 'eaten' && s.mealCardEaten]}>
              <View style={s.mealLeft}>
                <Text style={s.mealEmoji}>{MEAL_EMOJI[meal.meal_type] ?? '🍽'}</Text>
              </View>
              <View style={s.mealBody}>
                <View style={s.mealTopRow}>
                  <Text style={s.mealName}>
                    {meal.meal_time ?? '12:00'} · {meal.meal_name ?? MEAL_LABEL[meal.meal_type] ?? meal.meal_type}
                  </Text>
                  <View style={s.mealActions}>
                    {meal.status === 'eaten' && <Text style={s.eatenBadge}>✓ Съел</Text>}
                    <TouchableOpacity
                      style={[s.replaceMealBtn, replacingMealId === meal.id && s.replaceMealBtnDisabled]}
                      onPress={() => replaceMeal(meal.id)}
                      disabled={replacingMealId !== null || rebuildingDayId !== null || generating}
                      activeOpacity={0.75}
                    >
                      {replacingMealId === meal.id ? (
                        <ActivityIndicator color={PRIMARY} size="small" />
                      ) : (
                        <Text style={s.replaceMealText}>Заменить</Text>
                      )}
                    </TouchableOpacity>
                  </View>
                </View>
                <TouchableOpacity
                  style={[s.recipeToggle, isExpanded && s.recipeToggleOpen]}
                  onPress={() => setExpandedMealId(isExpanded ? null : meal.id)}
                  activeOpacity={0.75}
                >
                  {meal.description && (
                    <Text style={s.mealDescription}>{meal.description}</Text>
                  )}
                  <View style={s.mealMetaRow}>
                    {meal.kbzhu_actual ? (
                      <Text style={s.mealKcal}>{meal.kbzhu_actual.kcal} ккал</Text>
                    ) : (
                      <Text style={s.mealKcalPlan}>{Math.round(targets.kcal / selectedDay.meals.length)} ккал</Text>
                    )}
                    {recipe ? (
                      <View style={s.recipeHint}>
                        <Text style={s.recipeHintText}>Рецепт</Text>
                        <Text style={s.recipeChevron}>{isExpanded ? '⌃' : '⌄'}</Text>
                      </View>
                    ) : null}
                  </View>
                </TouchableOpacity>
                {isExpanded && recipe && (
                  <View style={s.recipeBox}>
                    {recipe.serving_grams ? (
                      <Text style={s.recipeMeta}>Порция: {recipe.serving_grams} г</Text>
                    ) : null}
                    {recipe.ingredients?.length ? (
                      <>
                        <Text style={s.recipeTitle}>Ингредиенты</Text>
                        {recipe.ingredients.slice(0, 12).map((ingredient, index) => (
                          <Text key={`${ingredient.name}-${index}`} style={s.recipeText}>
                            {ingredient.name} — {ingredient.quantity} {ingredient.unit}
                          </Text>
                        ))}
                      </>
                    ) : null}
                    {recipe.steps?.length ? (
                      <>
                        <Text style={s.recipeTitle}>Рецепт</Text>
                        {recipe.steps.slice(0, 8).map((step, index) => (
                          <Text key={`${step.order}-${index}`} style={s.recipeText}>
                            {step.order}. {step.text}
                          </Text>
                        ))}
                      </>
                    ) : null}
                  </View>
                )}
              </View>
            </View>
          );
          })
        )}

        {/* Day КБЖУ summary */}
        <View style={s.weekSummary}>
          <Text style={s.weekSummaryTitle}>Итого за день</Text>
          <View style={s.weekSummaryRow}>
            {[
              { label: 'Ккал', value: String(Math.round(dayTotals.kcal)) },
              { label: 'Белок', value: `${Math.round(dayTotals.protein)} г` },
              { label: 'Жир', value: `${Math.round(dayTotals.fat)} г` },
              { label: 'Углев', value: `${Math.round(dayTotals.carbs)} г` },
            ].map((item) => (
              <View key={item.label} style={s.weekSummaryStat}>
                <Text style={s.weekSummaryNum}>{item.value}</Text>
                <Text style={s.weekSummaryLabel}>{item.label}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Rebuild day button */}
        <TouchableOpacity
          style={[s.rebuildDayBtn, rebuildingDayId === selectedDay.id && s.regenBtnDisabled]}
          onPress={() => rebuildDay(selectedDay.id)}
          disabled={rebuildingDayId !== null || replacingMealId !== null || generating}
          activeOpacity={0.7}
        >
          {rebuildingDayId === selectedDay.id
            ? <ActivityIndicator color={PRIMARY} size="small" />
            : <Text style={s.rebuildDayText}>Пересобрать день</Text>
          }
        </TouchableOpacity>

        {/* Re-generate button */}
        <TouchableOpacity
          style={[s.regenBtn, generating && s.regenBtnDisabled]}
          onPress={() => generate('Пересобери меню по текущему профилю. Сделай больше разнообразия и проверь ограничения пользователя.')}
          disabled={generating}
          activeOpacity={0.7}
        >
          {generating
            ? <ActivityIndicator color={PRIMARY} size="small" />
            : <Text style={s.regenBtnText}>🔄 Пересоздать план</Text>
          }
        </TouchableOpacity>

        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  errorBanner: { backgroundColor: '#FEF2F2', color: RED, fontSize: 13, padding: 12, textAlign: 'center' },

  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 14 },
  title: { fontSize: 22, fontWeight: '800', color: BLACK, letterSpacing: -0.3 },
  period: { fontSize: 12, color: GRAY },

  weekScroll: { marginHorizontal: -16, marginBottom: 16 },
  weekRow: { paddingHorizontal: 16, gap: 8 },
  dayChip: { alignItems: 'center', paddingHorizontal: 10, paddingVertical: 8, borderRadius: 14, backgroundColor: CARD, minWidth: 46, borderWidth: 1, borderColor: '#E5E7EB' },
  dayChipActive: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  dayChipShort: { fontSize: 11, fontWeight: '600', color: GRAY },
  dayChipShortActive: { color: '#FFF' },
  dayChipDate: { fontSize: 16, fontWeight: '800', color: BLACK, marginTop: 1 },
  dayChipDateActive: { color: '#FFF' },

  dayHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  dayName: { fontSize: 15, fontWeight: '700', color: BLACK },
  dayMealCount: { fontSize: 12, color: GRAY },

  mealCard: { flexDirection: 'row', backgroundColor: CARD, borderRadius: 14, padding: 14, marginBottom: 8, gap: 12, alignItems: 'flex-start' },
  mealCardEaten: { opacity: 0.6 },
  mealLeft: { paddingTop: 2 },
  mealEmoji: { fontSize: 26 },
  mealBody: { flex: 1 },
  mealTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 },
  mealName: { flex: 1, fontSize: 13, fontWeight: '600', color: GRAY },
  mealActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  eatenBadge: { fontSize: 12, color: PRIMARY, fontWeight: '700' },
  replaceMealBtn: { minWidth: 72, minHeight: 28, borderRadius: 8, borderWidth: 1, borderColor: '#D1FAE5', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 10 },
  replaceMealBtnDisabled: { opacity: 0.55 },
  replaceMealText: { color: PRIMARY, fontSize: 12, fontWeight: '700' },
  mealKcal: { fontSize: 15, fontWeight: '700', color: BLACK },
  mealKcalPlan: { fontSize: 14, color: GRAY },
  mealDescription: { fontSize: 15, fontWeight: '700', color: BLACK, marginTop: 2 },
  mealContainer: { fontSize: 12, color: GRAY, marginTop: 2 },
  recipeToggle: { marginTop: 2, borderRadius: 8, paddingVertical: 4, paddingHorizontal: 6, marginLeft: -6 },
  recipeToggleOpen: { backgroundColor: '#F2FBF6' },
  mealMetaRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 2 },
  recipeHint: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, backgroundColor: '#EAF7EF' },
  recipeHintText: { fontSize: 12, fontWeight: '700', color: PRIMARY },
  recipeChevron: { fontSize: 15, fontWeight: '800', color: PRIMARY, lineHeight: 16 },
  recipeBox: { marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: '#EEF2F7' },
  recipeMeta: { fontSize: 12, fontWeight: '700', color: PRIMARY, marginBottom: 8 },
  recipeTitle: { fontSize: 13, fontWeight: '800', color: BLACK, marginTop: 8, marginBottom: 4 },
  recipeText: { fontSize: 13, color: GRAY, lineHeight: 19, marginBottom: 3 },

  noMeals: { padding: 24, alignItems: 'center' },
  noMealsText: { color: GRAY, fontSize: 14 },

  weekSummary: { backgroundColor: CARD, borderRadius: 16, padding: 16, marginTop: 6 },
  weekSummaryTitle: { fontSize: 14, fontWeight: '700', color: BLACK, marginBottom: 12 },
  weekSummaryRow: { flexDirection: 'row', justifyContent: 'space-around' },
  weekSummaryStat: { alignItems: 'center' },
  weekSummaryNum: { fontSize: 17, fontWeight: '800', color: PRIMARY },
  weekSummaryLabel: { fontSize: 11, color: GRAY, marginTop: 2 },

  rebuildDayBtn: { marginTop: 14, borderRadius: 12, paddingVertical: 12, alignItems: 'center', backgroundColor: '#EAF7EF' },
  rebuildDayText: { color: PRIMARY, fontSize: 14, fontWeight: '700' },
  regenBtn: { marginTop: 16, borderRadius: 12, paddingVertical: 12, alignItems: 'center', borderWidth: 1.5, borderColor: PRIMARY },
  regenBtnDisabled: { opacity: 0.5 },
  regenBtnText: { color: PRIMARY, fontSize: 14, fontWeight: '600' },
});
