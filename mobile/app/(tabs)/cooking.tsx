import { useEffect, useState, useCallback } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { cookingApi } from '@/api/cooking';

const PRIMARY = '#1A7340';
const BLUE = '#2563EB';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';

// ─── Types ───────────────────────────────────────────────────────────────────

interface CookingStep {
  id: number;
  step_number: number;
  title: string;
  description: string;
  duration_minutes: number;
  is_parallel: boolean;
  parallel_group: number | null;
  done: boolean;
}

interface CookingPlanData {
  id: number;
  scheduled_date: string | null;
  estimated_time_min: number;
  active_time_min: number;
  parallel_groups: number[][];
  container_distribution: Record<string, any>;
  steps: CookingStep[];
}

// ─── Screen ──────────────────────────────────────────────────────────────────

export default function CookingScreen() {
  const [plan, setPlan] = useState<CookingPlanData | null>(null);
  const [containers, setContainers] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [planData, containerData] = await Promise.allSettled([
        cookingApi.getPlan(),
        cookingApi.getContainerDistribution(),
      ]);
      if (planData.status === 'fulfilled') setPlan(planData.value);
      else if (planData.reason?.response?.status !== 404) setError('Не удалось загрузить план готовки');
      if (containerData.status === 'fulfilled') setContainers(containerData.value);
    } catch {
      setError('Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, []);

  const toggleStep = async (step: CookingStep) => {
    if (togglingId !== null || step.done) return;
    setTogglingId(step.id);
    // Optimistic update
    setPlan((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        steps: prev.steps.map((s) => s.id === step.id ? { ...s, done: true } : s),
      };
    });
    try {
      await cookingApi.markStepDone(step.id);
    } catch {
      // Rollback
      setPlan((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          steps: prev.steps.map((s) => s.id === step.id ? { ...s, done: false } : s),
        };
      });
    } finally {
      setTogglingId(null);
    }
  };

  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={s.safe}>
        <Text style={[s.title, { padding: 16 }]}>Готовка</Text>
        <ActivityIndicator color={PRIMARY} style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }

  // Empty state
  if (!plan || plan.steps.length === 0) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.content}>
          <Text style={s.title}>Готовка</Text>
          {error ? (
            <View style={s.emptyCard}>
              <Text style={[s.emptyText, { color: '#DC2626' }]}>{error}</Text>
              <TouchableOpacity onPress={loadData} style={{ marginTop: 12 }}>
                <Text style={{ color: PRIMARY, fontWeight: '600' }}>Повторить</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={s.emptyCard}>
              <Text style={s.emptyText}>Нет плана готовки</Text>
              <Text style={s.emptyHint}>Сначала создайте план питания на вкладке «План»</Text>
            </View>
          )}
        </View>
      </SafeAreaView>
    );
  }

  const steps = plan.steps;
  const doneCount = steps.filter((st) => st.done).length;
  const totalTime = plan.estimated_time_min || steps.reduce((sum, st) => sum + st.duration_minutes, 0);
  const activeTime = plan.active_time_min || totalTime;

  // Parse container distribution
  const containerList = parseContainers(containers);

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>

        <Text style={s.title}>Готовка</Text>

        {/* Header stats */}
        <View style={s.headerCard}>
          <View style={s.headerStat}>
            <Text style={s.headerStatNum}>{totalTime}</Text>
            <Text style={s.headerStatLabel}>мин всего</Text>
          </View>
          <View style={s.headerDivider} />
          <View style={s.headerStat}>
            <Text style={[s.headerStatNum, { color: PRIMARY }]}>{activeTime}</Text>
            <Text style={s.headerStatLabel}>мин активно</Text>
          </View>
          <View style={s.headerDivider} />
          <View style={s.headerStat}>
            <Text style={s.headerStatNum}>{doneCount}/{steps.length}</Text>
            <Text style={s.headerStatLabel}>шагов</Text>
          </View>
        </View>

        {/* Steps */}
        <Text style={s.sectionTitle}>Шаги</Text>

        {steps.map((step, idx) => {
          const isDone = step.done;
          const parallelLabel = step.is_parallel
            ? `Параллельно${step.parallel_group != null ? ` · группа ${step.parallel_group}` : ''}`
            : null;

          return (
            <View key={step.id} style={[s.stepCard, isDone && s.stepCardDone]}>
              <View style={s.stepLeft}>
                <TouchableOpacity
                  onPress={() => toggleStep(step)}
                  style={[s.stepNum, isDone && s.stepNumDone]}
                  activeOpacity={0.7}
                  disabled={isDone || togglingId !== null}
                >
                  <Text style={[s.stepNumText, isDone && s.stepNumTextDone]}>
                    {isDone ? '✓' : step.step_number}
                  </Text>
                </TouchableOpacity>
                {idx < steps.length - 1 && <View style={[s.connector, isDone && s.connectorDone]} />}
              </View>

              <View style={s.stepBody}>
                <View style={s.stepTopRow}>
                  <Text style={[s.stepTitle, isDone && s.stepTitleDone]}>{step.title}</Text>
                  <View style={[s.timeBadge, step.is_parallel && s.timeBadgeParallel]}>
                    <Text style={[s.timeBadgeText, step.is_parallel && s.timeBadgeTextParallel]}>
                      {step.duration_minutes} мин
                    </Text>
                  </View>
                </View>

                {parallelLabel && (
                  <View style={s.parallelNote}>
                    <Text style={s.parallelNoteText}>⚡ {parallelLabel}</Text>
                  </View>
                )}

                {!isDone && step.description ? (
                  step.description.split('\n').map((line, li) => (
                    <View key={li} style={s.taskRow}>
                      <View style={s.taskDot} />
                      <Text style={s.taskText}>{line}</Text>
                    </View>
                  ))
                ) : null}
              </View>
            </View>
          );
        })}

        {/* Container distribution */}
        {containerList.length > 0 && (
          <>
            <Text style={s.sectionTitle}>Раскладка по контейнерам</Text>
            <View style={s.containerGrid}>
              {containerList.map((c) => {
                const isFreezer = c.location?.toLowerCase().includes('морозил');
                return (
                  <View key={c.label} style={[s.containerCard, isFreezer && s.containerCardBlue]}>
                    <View style={s.containerTop}>
                      <View style={[s.containerBadge, isFreezer && s.containerBadgeBlue]}>
                        <Text style={[s.containerLabel, isFreezer && s.containerLabelBlue]}>{c.label}</Text>
                      </View>
                      {c.expiry && (
                        <View style={s.containerExpiry}>
                          <Text style={s.containerExpiryText}>до {c.expiry}</Text>
                        </View>
                      )}
                    </View>
                    <Text style={s.containerDesc}>{c.description}</Text>
                    {c.location && <Text style={s.containerLoc}>{c.location}</Text>}
                    {c.kcal != null && (
                      <View style={s.containerKbzhu}>
                        <Text style={[s.containerKbzhuText, isFreezer && { color: BLUE }]}>{c.kcal} ккал</Text>
                        {c.protein != null && <Text style={s.containerKbzhuSub}>Б{c.protein}г</Text>}
                      </View>
                    )}
                  </View>
                );
              })}
            </View>
          </>
        )}

        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Parse container distribution ────────────────────────────────────────────

interface ContainerInfo {
  label: string;
  description: string;
  location: string | null;
  expiry: string | null;
  kcal: number | null;
  protein: number | null;
}

function parseContainers(data: Record<string, any> | null): ContainerInfo[] {
  if (!data) return [];
  // Backend returns JSON — may be an array or a dict keyed by label
  if (Array.isArray(data)) {
    return data.map((c: any) => ({
      label: c.label ?? c.container_label ?? '?',
      description: c.description ?? c.contents ?? c.contents_description ?? '',
      location: c.location ?? c.storage_location ?? null,
      expiry: c.expiry_date ?? c.expiry ?? null,
      kcal: c.kbzhu?.kcal ?? c.kcal ?? null,
      protein: c.kbzhu?.protein ?? c.protein ?? null,
    }));
  }
  // Dict keyed by label: { "1А": { ... }, "2Б": { ... } }
  return Object.entries(data).map(([label, val]: [string, any]) => ({
    label,
    description: val?.description ?? val?.contents ?? '',
    location: val?.location ?? val?.storage_location ?? null,
    expiry: val?.expiry_date ?? val?.expiry ?? null,
    kcal: val?.kbzhu?.kcal ?? val?.kcal ?? null,
    protein: val?.kbzhu?.protein ?? val?.protein ?? null,
  }));
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16 },
  title: { fontSize: 22, fontWeight: '800', color: BLACK, letterSpacing: -0.3, marginBottom: 12 },

  emptyCard: { backgroundColor: CARD, borderRadius: 16, padding: 24, alignItems: 'center' },
  emptyText: { fontSize: 16, fontWeight: '600', color: BLACK, marginBottom: 6 },
  emptyHint: { fontSize: 13, color: GRAY, textAlign: 'center' },

  headerCard: { flexDirection: 'row', backgroundColor: CARD, borderRadius: 16, padding: 16, marginBottom: 16, boxShadow: '0 1px 6px rgba(0,0,0,0.04)' },
  headerStat: { flex: 1, alignItems: 'center' },
  headerStatNum: { fontSize: 22, fontWeight: '800', color: BLACK },
  headerStatLabel: { fontSize: 11, color: GRAY, marginTop: 1 },
  headerDivider: { width: 1, backgroundColor: '#E5E7EB' },

  sectionTitle: { fontSize: 16, fontWeight: '700', color: BLACK, marginBottom: 10, marginTop: 4 },

  stepCard: { flexDirection: 'row', marginBottom: 4, gap: 0 },
  stepCardDone: { opacity: 0.6 },
  stepLeft: { alignItems: 'center', width: 44 },
  stepNum: { width: 36, height: 36, borderRadius: 18, backgroundColor: PRIMARY, alignItems: 'center', justifyContent: 'center' },
  stepNumDone: { backgroundColor: '#6EE7B7' },
  stepNumText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  stepNumTextDone: { color: '#065F46' },
  connector: { width: 2, flex: 1, backgroundColor: '#D1FAE5', marginVertical: 2, minHeight: 16 },
  connectorDone: { backgroundColor: '#6EE7B7' },

  stepBody: { flex: 1, backgroundColor: CARD, borderRadius: 14, padding: 14, marginBottom: 6, marginLeft: 6 },
  stepTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  stepTitle: { fontSize: 15, fontWeight: '700', color: BLACK, flex: 1, marginRight: 8 },
  stepTitleDone: { color: GRAY },
  timeBadge: { backgroundColor: '#F3F4F6', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  timeBadgeParallel: { backgroundColor: '#ECFDF5' },
  timeBadgeText: { fontSize: 12, fontWeight: '600', color: GRAY },
  timeBadgeTextParallel: { color: PRIMARY },

  parallelNote: { backgroundColor: '#ECFDF5', borderRadius: 8, padding: 8, marginBottom: 8 },
  parallelNoteText: { fontSize: 12, color: PRIMARY, fontWeight: '500' },

  taskRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginBottom: 4 },
  taskDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: '#A7F3D0', marginTop: 6 },
  taskText: { fontSize: 13, color: GRAY, flex: 1, lineHeight: 18 },

  containerGrid: { gap: 8 },
  containerCard: { backgroundColor: '#F0FDF4', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: '#BBF7D0' },
  containerCardBlue: { backgroundColor: '#EFF6FF', borderColor: '#BFDBFE' },
  containerTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  containerBadge: { width: 42, height: 42, borderRadius: 12, backgroundColor: '#D1FAE5', alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: PRIMARY },
  containerBadgeBlue: { backgroundColor: '#DBEAFE', borderColor: '#3B82F6' },
  containerLabel: { fontSize: 16, fontWeight: '900', color: PRIMARY },
  containerLabelBlue: { color: BLUE },
  containerExpiry: { backgroundColor: '#FFF', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  containerExpiryText: { fontSize: 11, color: GRAY, fontWeight: '500' },
  containerDesc: { fontSize: 14, fontWeight: '700', color: BLACK, marginBottom: 2 },
  containerLoc: { fontSize: 12, color: GRAY, marginBottom: 6 },
  containerKbzhu: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  containerKbzhuText: { fontSize: 14, fontWeight: '700', color: PRIMARY },
  containerKbzhuSub: { fontSize: 12, color: GRAY },
});
