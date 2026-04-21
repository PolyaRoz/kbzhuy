import { useEffect, useState, useCallback } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { containersApi } from '@/api/containers';
import { usePlanStore } from '@/store/planStore';

const PRIMARY = '#1A7340';
const BLUE = '#2563EB';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';
const LIGHT_GRAY = '#F3F4F6';

// ─── Types ───────────────────────────────────────────────────────────────────

interface ContainerItem {
  id: number;
  label: string;
  meal_type: string;
  meal_id: number;
  status: string;
  contents_description: string | null;
  heating_instructions: string | null;
  kbzhu: { kcal: number; protein: number; fat: number; carbs: number } | null;
  location: string | null;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const MEAL_LABEL: Record<string, string> = {
  breakfast: 'Завтрак',
  lunch: 'Обед',
  snack: 'Перекус',
  dinner: 'Ужин',
};

const MEAL_TIME: Record<string, string> = {
  breakfast: '08:00',
  lunch: '13:00',
  snack: '16:00',
  dinner: '19:00',
};

const DAY_NAMES = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
const MONTH_NAMES = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];

function todayLabel(): string {
  const d = new Date();
  return `${DAY_NAMES[d.getDay()]}, ${d.getDate()} ${MONTH_NAMES[d.getMonth()]}`;
}

// ─── KbzhuBar ────────────────────────────────────────────────────────────────

function KbzhuBar({ label, current, total, color }: { label: string; current: number; total: number; color: string }) {
  const pct = total > 0 ? Math.min(current / total, 1) : 0;
  return (
    <View style={bar.row}>
      <Text style={bar.label}>{label}</Text>
      <View style={bar.track}>
        <View style={[bar.fill, { width: `${pct * 100}%` as any, backgroundColor: color }]} />
      </View>
      <Text style={bar.value}>{Math.round(current)}<Text style={bar.total}>/{Math.round(total)}</Text></Text>
    </View>
  );
}

const bar = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  label: { fontSize: 12, color: GRAY, fontWeight: '600', width: 28 },
  track: { flex: 1, height: 8, backgroundColor: LIGHT_GRAY, borderRadius: 4, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4 },
  value: { fontSize: 12, fontWeight: '700', color: BLACK, width: 60, textAlign: 'right' },
  total: { fontSize: 11, fontWeight: '400', color: GRAY },
});

// ─── Home Screen ─────────────────────────────────────────────────────────────

export default function HomeScreen() {
  const { plan, fetchPlan } = usePlanStore();
  const [containers, setContainers] = useState<ContainerItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [markingId, setMarkingId] = useState<number | null>(null);

  const loadContainers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await containersApi.getToday();
      setContainers(Array.isArray(data) ? data : []);
    } catch {
      setContainers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadContainers();
    if (!plan) fetchPlan();
  }, []);

  const handleEaten = async (item: ContainerItem) => {
    if (markingId !== null) return;
    setMarkingId(item.id);
    try {
      await containersApi.markEaten(item.id);
      setContainers((prev) =>
        prev.map((c) => (c.id === item.id ? { ...c, status: 'eaten' } : c))
      );
    } catch {
      // ignore — user can retry
    } finally {
      setMarkingId(null);
    }
  };

  // Compute consumed КБЖУ from eaten containers
  const eaten = containers.filter((c) => c.status === 'eaten');
  const consumed = eaten.reduce(
    (acc, c) => ({
      kcal: acc.kcal + (c.kbzhu?.kcal ?? 0),
      protein: acc.protein + (c.kbzhu?.protein ?? 0),
      fat: acc.fat + (c.kbzhu?.fat ?? 0),
      carbs: acc.carbs + (c.kbzhu?.carbs ?? 0),
    }),
    { kcal: 0, protein: 0, fat: 0, carbs: 0 }
  );

  const targets = plan?.daily_targets ?? { kcal: 0, protein: 0, fat: 0, carbs: 0 };

  // Current = first non-eaten container
  const currentIdx = containers.findIndex((c) => c.status !== 'eaten');

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView style={s.scroll} contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>

        {/* Header */}
        <View style={s.header}>
          <View>
            <Text style={s.headerTitle}>КБЖУЙ</Text>
            <Text style={s.headerDate}>{todayLabel()}</Text>
          </View>
          {targets.kcal > 0 && (
            <View style={s.calBadge}>
              <Text style={s.calBadgeNum}>{Math.round(consumed.kcal)}</Text>
              <Text style={s.calBadgeLabel}>/ {Math.round(targets.kcal)} ккал</Text>
            </View>
          )}
        </View>

        {/* КБЖУ Progress */}
        {targets.kcal > 0 && (
          <View style={s.card}>
            <View style={s.cardRow}>
              <Text style={s.cardTitle}>Прогресс дня</Text>
              <Text style={s.cardSubtitle}>цель {Math.round(targets.kcal)} ккал</Text>
            </View>
            <KbzhuBar label="ккал" current={consumed.kcal} total={targets.kcal} color={PRIMARY} />
            <KbzhuBar label="Б" current={consumed.protein} total={targets.protein} color="#3B82F6" />
            <KbzhuBar label="Ж" current={consumed.fat} total={targets.fat} color="#F59E0B" />
            <KbzhuBar label="У" current={consumed.carbs} total={targets.carbs} color="#8B5CF6" />
          </View>
        )}

        {/* Today's meals */}
        <Text style={s.sectionTitle}>Приёмы пищи</Text>

        {loading ? (
          <ActivityIndicator color={PRIMARY} style={{ marginTop: 24 }} />
        ) : containers.length === 0 ? (
          <View style={s.emptyCard}>
            <Text style={s.emptyText}>Нет данных на сегодня</Text>
            <Text style={s.emptyHint}>Сначала создайте план питания на вкладке «План»</Text>
          </View>
        ) : (
          containers.map((item, idx) => {
            const isCurrent = idx === currentIdx;
            const isDone = item.status === 'eaten';
            const label = MEAL_LABEL[item.meal_type] ?? item.meal_type;
            const time = MEAL_TIME[item.meal_type] ?? '';

            if (isCurrent) {
              return (
                <View key={item.id} style={[s.card, s.currentCard]}>
                  <View style={s.mealHeaderRow}>
                    <Text style={s.mealChip}>Сейчас · {label}</Text>
                    <Text style={s.mealTime}>{time}</Text>
                  </View>
                  <View style={s.mealMainRow}>
                    <View style={s.containerBadgeLarge}>
                      <Text style={s.containerBadgeLargeText}>{item.label}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.mealDesc}>{item.contents_description ?? label}</Text>
                      {item.location && <Text style={s.mealMeta}>{item.location}</Text>}
                      {item.heating_instructions && (
                        <View style={s.heatRow}>
                          <Text style={s.heatIcon}>🔥</Text>
                          <Text style={s.mealMeta}>{item.heating_instructions}</Text>
                        </View>
                      )}
                    </View>
                    {item.kbzhu && (
                      <View style={s.kcalBadge}>
                        <Text style={s.kcalNum}>{Math.round(item.kbzhu.kcal)}</Text>
                        <Text style={s.kcalLabel}>ккал</Text>
                      </View>
                    )}
                  </View>
                  <TouchableOpacity
                    style={[s.eatenBtn, markingId === item.id && s.eatenBtnDisabled]}
                    activeOpacity={0.8}
                    onPress={() => handleEaten(item)}
                    disabled={markingId !== null}
                  >
                    {markingId === item.id ? (
                      <ActivityIndicator color="#FFF" size="small" />
                    ) : (
                      <Text style={s.eatenBtnText}>Съел</Text>
                    )}
                  </TouchableOpacity>
                </View>
              );
            }

            return (
              <View key={item.id} style={[s.card, s.mutedCard, isDone && s.doneCard]}>
                <View style={s.mealMutedRow}>
                  <View style={[s.containerBadgeSmall, isDone && s.containerBadgeDone]}>
                    <Text style={[s.containerBadgeSmallText, isDone && s.containerBadgeDoneText]}>
                      {item.label}
                    </Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={[s.mealMutedName, isDone && s.mealMutedDone]}>
                      {time} · {label}
                    </Text>
                    <Text style={s.mealMutedDesc}>{item.contents_description ?? label}</Text>
                  </View>
                  {item.kbzhu && (
                    <Text style={s.kcalSmall}>{Math.round(item.kbzhu.kcal)} ккал</Text>
                  )}
                  {isDone && <Text style={s.checkIcon}>✓</Text>}
                  {!isDone && idx > currentIdx && (
                    <TouchableOpacity
                      style={s.eatenBtnSmall}
                      activeOpacity={0.8}
                      onPress={() => handleEaten(item)}
                      disabled={markingId !== null}
                    >
                      <Text style={s.eatenBtnSmallText}>Съел</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            );
          })
        )}

        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  scroll: { flex: 1 },
  content: { padding: 16 },

  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 },
  headerTitle: { fontSize: 28, fontWeight: '800', color: PRIMARY, letterSpacing: -0.5 },
  headerDate: { fontSize: 13, color: GRAY, marginTop: 2 },
  calBadge: { backgroundColor: PRIMARY, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 6, alignItems: 'center' },
  calBadgeNum: { fontSize: 18, fontWeight: '800', color: '#FFF' },
  calBadgeLabel: { fontSize: 10, color: 'rgba(255,255,255,0.8)', marginTop: -2 },

  card: { backgroundColor: CARD, borderRadius: 16, padding: 16, marginBottom: 10, boxShadow: '0 2px 8px rgba(0,0,0,0.05)' },
  cardRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  cardTitle: { fontSize: 15, fontWeight: '700', color: BLACK },
  cardSubtitle: { fontSize: 12, color: GRAY },

  sectionTitle: { fontSize: 16, fontWeight: '700', color: BLACK, marginBottom: 8, marginTop: 4 },

  emptyCard: { backgroundColor: CARD, borderRadius: 16, padding: 24, alignItems: 'center' },
  emptyText: { fontSize: 16, fontWeight: '600', color: BLACK, marginBottom: 6 },
  emptyHint: { fontSize: 13, color: GRAY, textAlign: 'center' },

  // Current meal
  currentCard: { borderWidth: 2, borderColor: PRIMARY },
  mealHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  mealChip: { backgroundColor: '#D1FAE5', color: PRIMARY, fontSize: 12, fontWeight: '700', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20 },
  mealTime: { fontSize: 13, color: GRAY },
  mealMainRow: { flexDirection: 'row', gap: 12, alignItems: 'flex-start', marginBottom: 14 },
  containerBadgeLarge: { width: 52, height: 52, borderRadius: 14, backgroundColor: '#D1FAE5', alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: PRIMARY },
  containerBadgeLargeText: { fontSize: 20, fontWeight: '900', color: PRIMARY },
  mealDesc: { fontSize: 16, fontWeight: '700', color: BLACK, marginBottom: 3 },
  mealMeta: { fontSize: 12, color: GRAY },
  heatRow: { flexDirection: 'row', alignItems: 'center', gap: 3, marginTop: 1 },
  heatIcon: { fontSize: 11 },
  kcalBadge: { alignItems: 'center' },
  kcalNum: { fontSize: 20, fontWeight: '800', color: BLACK },
  kcalLabel: { fontSize: 10, color: GRAY },
  eatenBtn: { backgroundColor: PRIMARY, borderRadius: 12, paddingVertical: 13, alignItems: 'center' },
  eatenBtnDisabled: { opacity: 0.6 },
  eatenBtnText: { color: '#FFF', fontWeight: '700', fontSize: 16, letterSpacing: 0.3 },

  // Muted meal cards
  mutedCard: { paddingVertical: 12 },
  doneCard: { opacity: 0.7 },
  mealMutedRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  containerBadgeSmall: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#F3F4F6', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#E5E7EB' },
  containerBadgeDone: { backgroundColor: '#D1FAE5', borderColor: '#6EE7B7' },
  containerBadgeSmallText: { fontSize: 13, fontWeight: '800', color: GRAY },
  containerBadgeDoneText: { color: PRIMARY },
  mealMutedName: { fontSize: 13, fontWeight: '600', color: BLACK },
  mealMutedDone: { color: GRAY },
  mealMutedDesc: { fontSize: 12, color: GRAY, marginTop: 1 },
  kcalSmall: { fontSize: 12, color: GRAY },
  checkIcon: { fontSize: 16, color: PRIMARY, marginLeft: 4 },
  eatenBtnSmall: { backgroundColor: '#D1FAE5', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5 },
  eatenBtnSmallText: { fontSize: 12, fontWeight: '700', color: PRIMARY },
});
