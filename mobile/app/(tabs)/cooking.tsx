import { Ionicons } from '@expo/vector-icons';
import { useCallback, useEffect, useMemo, useState } from 'react';


import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';


import { SafeAreaView } from 'react-native-safe-area-context';


import { router, useFocusEffect } from 'expo-router';


import { cookingApi } from '@/api/cooking';


import { storageApi } from '@/api/storage';


import { useStorageStore } from '@/store/storageStore';
import { usePlanStore } from '@/store/planStore';





const PRIMARY = '#2B3A2E';


const BLUE = '#4A5C4D';


const BG = '#FAFAF7';


const CARD = '#FFFFFF';


const BLACK = '#1A1A1A';


const GRAY = '#6E7E70';


const BORDER = '#D4DAD5';





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





interface CookingModule {


  name: string;


  portions: number;


  meal_labels: string[];


  containers?: CookingContainer[];


  ingredients: string[];


  storage: string;


  storage_note: string;


  fresh_finish: boolean;


  freezer_friendly: boolean;


  module_type: string;


}





interface CookingContainer {


  label: string;


  meal_label: string;


  grams?: number | null;


  date?: string | null;


  meal_name?: string | null;


  storage_location?: 'fridge' | 'freezer' | 'pantry' | 'later' | null;


}





interface CookingSession {


  index: number;


  date: string;


  date_label: string;


  title: string;


  estimated_time_min: number;


  active_time_min: number;


  meals_covered: number;


  modules: CookingModule[];


  step_numbers: number[];


}





interface CookingMeta {


  summary?: {


    strategy?: string;


    sessions_count?: number;


    meals_count?: number;


    batch_modules_count?: number;


    principle?: string;


  };


  sessions?: CookingSession[];


  modules?: CookingModule[];


  principles?: string[];


}





interface CookingPlanData {


  id: number;


  scheduled_date: string | null;


  estimated_time_min: number;


  active_time_min: number;


  parallel_groups: number[];


  container_distribution: CookingMeta;


  steps: CookingStep[];


}





interface ActiveTimer {


  id: string;


  title: string;


  remainingSec: number;


  totalSec: number;


}





export default function CookingScreen() {

  const globalPlan = usePlanStore((s) => s.plan);

  const [plan, setPlan] = useState<CookingPlanData | null>(null);


  const [loading, setLoading] = useState(true);


  const [error, setError] = useState<string | null>(null);


  const [togglingId, setTogglingId] = useState<number | null>(null);


  const [expandedProducts, setExpandedProducts] = useState<Record<number, boolean>>({});
  const [expandedSessions, setExpandedSessions] = useState<Record<number, boolean>>({ 1: true });


  const [timers, setTimers] = useState<ActiveTimer[]>([]);


  const [packedGroups, setPackedGroups] = useState<Set<string>>(new Set());


  const [packedItemIds, setPackedItemIds] = useState<Record<string, number[]>>({});


  const [packingGroup, setPackingGroup] = useState<string | null>(null);





  const loadData = useCallback(async () => {


    setLoading(true);


    setError(null);


    try {


      const planData = await cookingApi.getPlan();


      setPlan(planData);


    } catch (err: any) {


      setPlan(null);


      if (err?.response?.status === 404) {


        setError('Сначала нужен активный план питания');


      } else {


        setError('Не удалось открыть план готовки');


      }


    } finally {


      setLoading(false);


    }


  }, []);





  useFocusEffect(


    useCallback(() => {


      void loadData();


    }, [loadData]),


  );

  // When a new plan is created in another tab, reload cooking plan automatically
  useEffect(() => {
    if (globalPlan) {
      void loadData();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [globalPlan]);



  useEffect(() => {


    if (timers.length === 0) return;


    const interval = setInterval(() => {


      setTimers((prev) => prev


        .map((timer) => ({ ...timer, remainingSec: Math.max(timer.remainingSec - 1, 0) }))


        .filter((timer) => timer.remainingSec > 0));


    }, 1000);


    return () => clearInterval(interval);


  }, [timers.length]);





  const handlePackGroup = async (module: CookingModule, location: string, containers: CookingContainer[]) => {


    const key = `${module.name}:${location}`;


    if (packedGroups.has(key) || packingGroup) return;


    setPackingGroup(key);


    try {


      const createdIds: number[] = [];


      for (const container of containers) {


        const result = await storageApi.addItem({


          name: `${container.label}: ${module.name}`,


          quantity: Number(container.grams ?? 1),


          unit: container.grams ? 'г' : 'порц.',


          location_type: location as 'fridge' | 'freezer' | 'pantry',


          category: 'Готовая еда',

          raw: true,

        });


        const itemId = Number((result as any)?.item_id);


        if (itemId) createdIds.push(itemId);


      }


      setPackedGroups((prev) => new Set([...prev, key]));


      setPackedItemIds((prev) => ({ ...prev, [key]: createdIds }));


      void useStorageStore.getState().fetchAll();


    } finally {


      setPackingGroup(null);


    }


  };


  const handleUnpackGroup = async (module: CookingModule, location: string) => {


    const key = `${module.name}:${location}`;


    if (!packedGroups.has(key) || packingGroup) return;


    setPackingGroup(key);


    try {


      const ids = packedItemIds[key] ?? [];


      for (const id of ids) {


        await storageApi.deleteItem(id);


      }


      setPackedGroups((prev) => {


        const next = new Set(prev);


        next.delete(key);


        return next;


      });


      setPackedItemIds((prev) => {


        const next = { ...prev };


        delete next[key];


        return next;


      });


      void useStorageStore.getState().fetchAll();


    } finally {


      setPackingGroup(null);


    }


  };


  const toggleStep = async (step: CookingStep) => {


    if (togglingId !== null) return;


    const nextDone = !step.done;


    setTogglingId(step.id);


    if (nextDone && shouldStartTimer(step)) {


      setTimers((prev) => {


        const timerId = `step-${step.id}`;


        if (prev.some((timer) => timer.id === timerId)) return prev;


        const seconds = Math.max(1, step.duration_minutes || 1) * 60;


        return [


          ...prev,


          {


            id: timerId,


            title: timerTitle(step),


            remainingSec: seconds,


            totalSec: seconds,


          },


        ];


      });


    } else if (!nextDone) {


      setTimers((prev) => prev.filter((timer) => timer.id !== `step-${step.id}`));


    }


    setPlan((prev) => {


      if (!prev) return prev;


      return {


        ...prev,


        steps: prev.steps.map((item) => item.id === step.id ? { ...item, done: nextDone } : item),


      };


    });


    try {


      await syncPackingStepStorage(plan, step, nextDone);


      await cookingApi.setStepDone(step.id, nextDone);


      void useStorageStore.getState().fetchAll();


    } catch {


      setPlan((prev) => {


        if (!prev) return prev;


        return {


          ...prev,


          steps: prev.steps.map((item) => item.id === step.id ? { ...item, done: step.done } : item),


        };


      });


    } finally {


      setTogglingId(null);


    }


  };





  const groupedSteps = useMemo(() => {


    const groups: Record<number, CookingStep[]> = {};


    for (const step of plan?.steps ?? []) {


      const index = step.parallel_group ?? 1;


      groups[index] = groups[index] ?? [];


      groups[index].push(step);


    }


    return groups;


  }, [plan?.steps]);

  // Pre-compute interleaved step+packing items for every session
  const sessionItemsMap = useMemo(() => {
    type PackItem = { module: CookingModule; loc: string; containers: CookingContainer[] };
    type Item =
      | { kind: 'real'; step: CookingStep; num: number }
      | { kind: 'pack'; module: CookingModule; loc: string; containers: CookingContainer[]; num: number };

    const planSessions = plan?.container_distribution?.sessions ?? [];
    const result: Record<number, Item[]> = {};
    for (const session of planSessions) {
      const realSteps = [...(groupedSteps[session.index] ?? [])].sort((a, b) => a.step_number - b.step_number);

      const moduleLastIdx: Record<string, number> = {};
      for (const module of session.modules) {
        const name = module.name.toLowerCase();
        let lastIdx = -1;
        for (let i = 0; i < realSteps.length; i++) {
          const st = realSteps[i];
          if (st.title.toLowerCase().includes(name) || st.description.toLowerCase().includes(name)) lastIdx = i;
        }
        moduleLastIdx[module.name] = lastIdx;
      }

      const insertAfter: Record<number, PackItem[]> = {};
      const appendPack: PackItem[] = [];
      for (const module of session.modules) {
        const locGroups = groupContainersByStorage(module);
        if (locGroups.length === 0) continue;
        const idx = moduleLastIdx[module.name];
        let targetIdx = idx;
        if (idx >= 0 && realSteps[idx].is_parallel) {
          const waitTime = realSteps[idx].duration_minutes + 10;
          let accumulated = 0;
          targetIdx = realSteps.length - 1;
          for (let j = idx + 1; j < realSteps.length; j++) {
            if (!realSteps[j].is_parallel) accumulated += realSteps[j].duration_minutes;
            if (accumulated >= waitTime) { targetIdx = j; break; }
          }
        }
        for (const { loc, containers } of locGroups) {
          if (targetIdx >= 0) {
            if (!insertAfter[targetIdx]) insertAfter[targetIdx] = [];
            insertAfter[targetIdx].push({ module, loc, containers });
          } else {
            appendPack.push({ module, loc, containers });
          }
        }
      }

      const shiftedInsertAfter: Record<number, PackItem[]> = {};
      for (const [idxStr, packItems] of Object.entries(insertAfter)) {
        let i = Number(idxStr);
        if (i + 1 < realSteps.length && realSteps[i + 1].is_parallel) i = i + 1;
        if (!shiftedInsertAfter[i]) shiftedInsertAfter[i] = [];
        shiftedInsertAfter[i].push(...packItems);
      }

      const items: Item[] = [];
      let seq = 0;
      for (let i = 0; i < realSteps.length; i++) {
        seq += 1;
        items.push({ kind: 'real', step: realSteps[i], num: seq });
        for (const p of (shiftedInsertAfter[i] ?? [])) { seq += 1; items.push({ kind: 'pack', ...p, num: seq }); }
      }
      for (const p of appendPack) { seq += 1; items.push({ kind: 'pack', ...p, num: seq }); }
      result[session.index] = items;
    }
    return result;
  }, [plan, groupedSteps]);




  if (loading) {


    return (


      <SafeAreaView style={s.safe}>


        <Text style={[s.title, { padding: 16 }]}>Готовка</Text>


        <ActivityIndicator color={PRIMARY} style={{ marginTop: 40 }} />


      </SafeAreaView>


    );


  }





  if (!plan || plan.steps.length === 0) {
    const isNoPlan = !plan && error === 'Сначала нужен активный план питания';

    return (


      <SafeAreaView style={s.safe}>


        <View style={s.content}>


          <Text style={s.title}>Готовка</Text>

          {isNoPlan ? (
            <View style={s.noPlanCard}>
              <View style={s.noPlanIconWrap}>
                <Ionicons name="flame-outline" size={32} color={PRIMARY} />
              </View>
              <Text style={s.noPlanTitle}>Нет плана питания</Text>
              <Text style={s.noPlanHint}>План готовки собирается автоматически из меню: шаги, время и фасовка по контейнерам.</Text>
              <TouchableOpacity style={s.noPlanBtn} onPress={() => router.push('/(tabs)/plan')} activeOpacity={0.85}>
                <Text style={s.noPlanBtnText}>Создать план</Text>
              </TouchableOpacity>
            </View>
          ) : (
          <View style={s.emptyCard}>


            <Text style={[s.emptyText, error ? { color: '#C8553D' } : null]}>


              {error ?? 'Нет плана готовки'}


            </Text>


            <Text style={s.emptyHint}>


              План готовки собирается из текущего меню и рецептов: конкретные шаги, время и фасовка.


            </Text>


            <TouchableOpacity onPress={loadData} style={s.secondaryButton}>


              <Text style={s.secondaryButtonText}>Повторить</Text>


            </TouchableOpacity>


          </View>
          )}


        </View>


      </SafeAreaView>


    );


  }





  const meta = plan.container_distribution ?? {};


  const sessions = meta.sessions ?? [];


  const modules = meta.modules ?? [];


  const doneCount = plan.steps.filter((step) => step.done).length;





  return (


    <SafeAreaView style={s.safe}>


      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>


        <View style={s.titleRow}>


          <Text style={s.title}>Готовка</Text>


        </View>





        <View style={s.headerCard}>


          <View style={s.headerStat}>


            <Text style={s.headerStatNum}>{formatMinutes(plan.active_time_min)}</Text>


            <Text style={s.headerStatLabel}>активная работа</Text>


          </View>


          <View style={s.headerDivider} />


          <View style={s.headerStat}>


            <Text style={[s.headerStatNum, s.headerStatNumTotal]}>{formatMinutes(plan.estimated_time_min)}</Text>


            <Text style={s.headerStatLabel}>активно + пассивно</Text>


          </View>


          <View style={s.headerDivider} />


          <View style={s.headerStat}>


            <Text style={s.headerStatNum}>{doneCount}/{plan.steps.length}</Text>


            <Text style={s.headerStatLabel}>шагов</Text>


          </View>


        </View>





        {error ? <Text style={s.errorText}>{error}</Text> : null}





        {sessions.length > 0 && (


          <>


            <Text style={s.sectionTitle}>Когда готовим</Text>


            <View style={s.sessionList}>


              {sessions.map((session) => (


                <View key={session.index} style={s.sessionCard}>


                  <View style={s.sessionTop}>


                    <View>


                      <Text style={s.sessionDate}>{session.date_label}</Text>


                      <Text style={s.sessionTitle}>{session.title}</Text>


                    </View>


                    <View style={s.sessionBadge}>


                      <Text style={s.sessionBadgeText}>{formatMinutes(session.active_time_min)}</Text>


                      <Text style={s.sessionBadgeLabel}>активно</Text>


                    </View>


                  </View>


                  <Text style={s.sessionSub}>


                    {session.meals_covered} приемов · {session.modules.length} заготовок


                  </Text>


                  {session.modules.length > 0 && (


                    <>


                      <View style={s.chipRow}>


                        {session.modules.slice(0, 5).map((module) => (


                          <View key={`${session.index}-${module.name}`} style={s.chip}>


                            <Text style={s.chipText}>{module.name}</Text>


                          </View>


                        ))}


                      </View>


                      <TouchableOpacity


                        onPress={() => setExpandedProducts((prev) => ({ ...prev, [session.index]: !prev[session.index] }))}


                        style={s.productsToggle}


                        activeOpacity={0.8}


                      >


                        <Text style={s.productsToggleText}>


                          {expandedProducts[session.index] ? 'Скрыть продукты' : 'Продукты для этой заготовки'}


                        </Text>


                        <Text style={s.productsToggleIcon}>{expandedProducts[session.index] ? '▴' : '▾'}</Text>


                      </TouchableOpacity>


                      {expandedProducts[session.index] ? (


                        <View style={s.productsBox}>


                          {session.modules.map((module) => (


                            <View key={`products-${session.index}-${module.name}`} style={s.productsModule}>


                              <Text style={s.productsModuleTitle}>{module.name}</Text>


                              <Text style={s.productsModuleText}>


                                {(module.ingredients ?? []).slice(0, 14).join(', ') || 'Продукты указаны в шагах ниже'}


                              </Text>


                            </View>


                          ))}


                        </View>


                      ) : null}

                      {/* Collapsible steps — same toggle style as products */}
                      <TouchableOpacity
                        onPress={() => setExpandedSessions((prev) => ({ ...prev, [session.index]: !prev[session.index] }))}
                        style={s.productsToggle}
                        activeOpacity={0.8}
                      >
                        <Text style={s.productsToggleText}>
                          {expandedSessions[session.index]
                            ? 'Скрыть план готовки'
                            : `План готовки · ${sessionItemsMap[session.index]?.length ?? 0} шагов`}
                        </Text>
                        <Text style={s.productsToggleIcon}>{expandedSessions[session.index] ? '▴' : '▾'}</Text>
                      </TouchableOpacity>

                      {expandedSessions[session.index] && (
                        <View style={s.stepsBox}>
                          {(sessionItemsMap[session.index] ?? []).map((item) => {
                            if (item.kind === 'real') {
                              return (
                                <StepCard
                                  key={item.step.id}
                                  step={item.step}
                                  displayNumber={item.num}
                                  togglingId={togglingId}
                                  onToggle={toggleStep}
                                />
                              );
                            }
                            const key = `${item.module.name}:${item.loc}`;
                            return (
                              <PackingStepCard
                                key={key}
                                stepNumber={item.num}
                                moduleName={item.module.name}
                                location={item.loc}
                                containers={item.containers}
                                freezerFriendly={item.module.freezer_friendly}
                                freshFinish={item.module.fresh_finish}
                                isPacked={packedGroups.has(key)}
                                isLoading={packingGroup === key}
                                disabled={!!packingGroup}
                                onPack={() => handlePackGroup(item.module, item.loc, item.containers)}
                                onUnpack={() => handleUnpackGroup(item.module, item.loc)}
                              />
                            );
                          })}
                        </View>
                      )}

                    </>


                  )}


                </View>


              ))}


            </View>


          </>


        )}










        {modules.length > 0 && (


          <>


            <Text style={s.sectionTitle}>Что получится</Text>


            <View style={s.moduleList}>


              {modules.map((module) => (


                <View key={module.name} style={s.moduleCard}>


                  <View style={s.moduleTop}>


                    <Text style={s.moduleTitle}>{module.name}</Text>


                    <Text style={s.modulePortions}>{module.portions} порц.</Text>


                  </View>


                  <Text style={s.moduleType}>{module.module_type} · {module.storage}</Text>





                  <Text style={s.moduleMeals}>{module.meal_labels.join('; ')}</Text>


                </View>


              ))}


            </View>


          </>


        )}






        <View style={{ height: 24 }} />


      </ScrollView>


      <TimerOverlay timers={timers} />


    </SafeAreaView>


  );


}





const STORAGE_LOC_META: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap; color: string }> = {
  fridge: { label: 'Холодильник', icon: 'snow-outline', color: '#2B3A2E' },
  freezer: { label: 'Морозилка', icon: 'thermometer-outline', color: '#4A5C4D' },
  pantry: { label: 'Шкаф', icon: 'layers-outline', color: '#C9A14B' },
};

function resolveStorageLocation(module: CookingModule, container: CookingContainer, containerIndex: number = 0): 'fridge' | 'freezer' | 'pantry' {
  if (container.storage_location === 'fridge' || container.storage_location === 'freezer' || container.storage_location === 'pantry') {
    return container.storage_location;
  }
  if (container.date) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const containerDate = new Date(`${container.date}T00:00:00`);
    const diffDays = Math.round((containerDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays <= 3) return 'fridge';
    if (module.freezer_friendly) return 'freezer';
    return 'fridge';
  }
  // No date set: for freezer_friendly modules split by index —
  // first 3 containers → fridge (near-term), the rest → freezer
  if (module.freezer_friendly && containerIndex >= 3) return 'freezer';
  return 'fridge';
}

function groupContainersByStorage(module: CookingModule): Array<{ loc: string; containers: CookingContainer[] }> {
  const map: Record<string, CookingContainer[]> = {};
  const containers = module.containers ?? [];
  for (let i = 0; i < containers.length; i++) {
    const loc = resolveStorageLocation(module, containers[i], i);
    if (!map[loc]) map[loc] = [];
    map[loc].push(containers[i]);
  }
  const order = ['fridge', 'freezer', 'pantry'];
  return order.filter((loc) => map[loc]?.length).map((loc) => ({ loc, containers: map[loc] }));
}

function formatDate(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(`${iso}T00:00:00`);
  const month = String(d.getMonth() + 1).padStart(2, '0');
  return `${d.getDate()}.${month}`;
}

function formatMinutes(value: number) {


  const minutes = Math.max(0, Math.round(value || 0));


  if (minutes < 60) return `${minutes} мин`;


  const hours = Math.floor(minutes / 60);


  const rest = minutes % 60;


  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`;


}





function formatTimer(seconds: number) {


  const safe = Math.max(0, Math.round(seconds));


  const minutes = Math.floor(safe / 60);


  const rest = safe % 60;


  return `${minutes}:${String(rest).padStart(2, '0')}`;


}





function shouldStartTimer(step: CookingStep) {


  const text = `${step.title} ${step.description}`.toLowerCase();


  return step.is_parallel || /духовк|варить|тушить|запечь|выпек|марин|охлад|наста|томить|кипени|жарить \d|обжарить \d/.test(text);


}





function timerTitle(step: CookingStep) {


  return step.title.replace(/[«»]/g, '').replace(/\s+/g, ' ').slice(0, 34);


}





function isPackingStep(step: CookingStep) {


  const text = `${step.title}\n${step.description}`.toLowerCase();


  return text.includes('разлож') || text.includes('убрать в');


}





function stepStorageKey(planId: number, stepId: number) {


  return `cooking_packing_step_${planId}_${stepId}`;


}





function getStoredStepItemIds(planId: number, stepId: number): number[] {


  if (typeof localStorage === 'undefined') return [];


  try {


    const raw = localStorage.getItem(stepStorageKey(planId, stepId));


    const parsed = raw ? JSON.parse(raw) : [];


    return Array.isArray(parsed) ? parsed.map(Number).filter(Boolean) : [];


  } catch {


    return [];


  }


}





function setStoredStepItemIds(planId: number, stepId: number, ids: number[]) {


  if (typeof localStorage === 'undefined') return;


  localStorage.setItem(stepStorageKey(planId, stepId), JSON.stringify(ids));


}





function clearStoredStepItemIds(planId: number, stepId: number) {


  if (typeof localStorage === 'undefined') return;


  localStorage.removeItem(stepStorageKey(planId, stepId));


}





function moduleForPackingStep(plan: CookingPlanData, step: CookingStep): CookingModule | null {


  const modules = plan.container_distribution?.modules ?? [];


  return modules.find((module) => step.title.includes(module.name) || step.description.includes(module.name)) ?? null;


}





async function syncPackingStepStorage(plan: CookingPlanData | null, step: CookingStep, done: boolean) {


  if (!plan || !isPackingStep(step)) return;


  const module = moduleForPackingStep(plan, step);


  if (!module) return;





  if (!done) {


    for (const itemId of getStoredStepItemIds(plan.id, step.id)) {


      await storageApi.deleteItem(itemId);


    }


    for (const ingredient of module.ingredients ?? []) {


      const parsed = parseIngredient(ingredient);


      if (parsed) {


        await storageApi.addItem({ ...parsed, location_type: undefined, category: null });


      }


    }


    clearStoredStepItemIds(plan.id, step.id);


    return;


  }





  const itemIds: number[] = [];


  for (const container of module.containers ?? []) {


    const locationType = container.storage_location;


    if (locationType !== 'fridge' && locationType !== 'freezer' && locationType !== 'pantry') continue;


    const result = await storageApi.addItem({


      name: `${container.label}: ${module.name}`,


      quantity: Number(container.grams ?? 1),


      unit: container.grams ? 'г' : 'порц.',


      location_type: locationType,


      category: 'Готовая еда',


    });


    const itemId = Number(result?.item_id);


    if (itemId) itemIds.push(itemId);


  }


  for (const ingredient of module.ingredients ?? []) {


    const parsed = parseIngredient(ingredient);


    if (parsed) {


      await storageApi.useByName(parsed);


    }


  }


  setStoredStepItemIds(plan.id, step.id, itemIds);


}





function parseIngredient(value: string): { name: string; quantity: number; unit: string } | null {


  const match = value.trim().match(/^(.+?)\s+([\d.,]+)\s*([^\d\s.,]+)\s*$/);


  if (!match) return null;


  const quantity = Number(match[2].replace(',', '.'));


  if (!quantity || quantity <= 0) return null;


  return {


    name: match[1].trim(),


    quantity,


    unit: match[3].trim(),


  };


}





function TimerOverlay({ timers }: { timers: ActiveTimer[] }) {


  if (timers.length === 0) return null;


  return (


    <View style={s.timerOverlay} pointerEvents="none">


      {timers.slice(0, 4).map((timer) => (


        <View key={timer.id} style={s.timerWidget}>


          <Text style={s.timerTime}>{formatTimer(timer.remainingSec)}</Text>


          <Text style={s.timerTitle} numberOfLines={1}>{timer.title}</Text>


        </View>


      ))}


    </View>


  );


}





function StepCard({


  step,


  togglingId,


  onToggle,


  displayNumber,


}: {


  step: CookingStep;


  togglingId: number | null;


  onToggle: (step: CookingStep) => void;


  displayNumber?: number;


}) {


  const isDone = step.done;


  return (


    <View style={[s.stepCard, isDone && s.stepCardDone]}>


      <View style={s.stepIndex}>


        <Text style={s.stepIndexText}>{displayNumber ?? step.step_number}</Text>


      </View>


      <TouchableOpacity


        onPress={() => onToggle(step)}


        style={[s.stepCheck, isDone && s.stepCheckDone]}


        activeOpacity={0.7}


        disabled={togglingId !== null}


      >


        <Text style={[s.stepCheckText, isDone && s.stepCheckTextDone]}>{isDone ? '✓' : ''}</Text>


      </TouchableOpacity>


      <View style={s.stepBody}>


        <View style={s.stepTopRow}>


          <Text style={[s.stepTitle, isDone && s.stepTitleDone]}>{step.title}</Text>


          <View style={[s.timeBadge, step.is_parallel && s.timeBadgeParallel]}>


            <Text style={[s.timeBadgeText, step.is_parallel && s.timeBadgeTextParallel]}>


              {step.is_parallel ? 'пассивно' : 'активно'} · {step.duration_minutes} мин


            </Text>


          </View>


        </View>


        {step.description ? (


          step.description.split('\n').map((line) => (


            <View key={line} style={s.taskRow}>


              <View style={s.taskDot} />


              <Text style={s.taskText}>{line}</Text>


            </View>


          ))


        ) : null}


      </View>


    </View>


  );


}





function PackingStepCard({
  stepNumber,
  moduleName,
  location,
  containers,
  freshFinish,
  isPacked,
  isLoading,
  disabled,
  onPack,
  onUnpack,
}: {
  stepNumber: number;
  moduleName: string;
  location: string;
  containers: CookingContainer[];
  freezerFriendly: boolean;
  freshFinish: boolean;
  isPacked: boolean;
  isLoading: boolean;
  disabled: boolean;
  onPack: () => void;
  onUnpack: () => void;
}) {
  const meta = STORAGE_LOC_META[location] ?? STORAGE_LOC_META.fridge;

  return (
    <View style={[s.stepCard, isPacked && s.stepCardDone]}>
      <View style={[s.stepIndex, { backgroundColor: meta.color }]}>
        <Text style={s.stepIndexText}>{stepNumber}</Text>
      </View>

      <TouchableOpacity
        onPress={isPacked ? onUnpack : onPack}
        style={[s.stepCheck, isPacked && s.stepCheckDone]}
        activeOpacity={0.7}
        disabled={disabled}
      >
        {isPacked ? <Text style={[s.stepCheckText, s.stepCheckTextDone]}>✓</Text> : null}
      </TouchableOpacity>

      <View style={s.stepBody}>
        <View style={s.stepTopRow}>
          <Text style={[s.stepTitle, isPacked && s.stepTitleDone]}>
            {moduleName} → {meta.label.toLowerCase()}
          </Text>
          <View style={[s.timeBadge, { backgroundColor: '#E8E4D9', flexDirection: 'row', alignItems: 'center', gap: 4 }]}>
            <Ionicons name={meta.icon} size={12} color={meta.color} />
          </View>
        </View>

        <View style={s.packingContainerList}>
          {containers.map((c) => (
            <View key={c.label} style={s.packingContainerRow}>
              <View style={s.packingLabelPill}>
                <Text style={s.packingLabelPillText}>{c.label}</Text>
              </View>
              {c.grams ? (
                <Text style={s.packingGramsBig}>{c.grams} г</Text>
              ) : null}
              {c.date ? (
                <Text style={s.packingDateTag}>{formatDate(c.date)}</Text>
              ) : null}
            </View>
          ))}
        </View>

        {isPacked ? (
          <View style={s.packingDoneRow}>
            <Text style={s.packingDoneText}>✓ Разложено · {containers.length} контейн.</Text>
            <TouchableOpacity style={s.packingUndoBtn} onPress={onUnpack} disabled={disabled}>
              <Text style={s.packingUndoText}>Отменить</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity
            style={[s.packingBtn, { borderColor: meta.color }]}
            onPress={onPack}
            disabled={disabled}
            activeOpacity={0.8}
          >
            {isLoading ? (
              <ActivityIndicator size="small" color={meta.color} />
            ) : (
              <>
                <Ionicons name={meta.icon} size={15} color={meta.color} />
                <Text style={[s.packingBtnText, { color: meta.color }]}>
                  Положить в {meta.label.toLowerCase()} ({containers.length})
                </Text>
              </>
            )}
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const s = StyleSheet.create({


  safe: { flex: 1, backgroundColor: BG },


  content: { padding: 16 },


  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },


  title: { fontSize: 28, fontWeight: '900', color: BLACK, letterSpacing: -0.56, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },


  iconButton: { width: 42, height: 42, borderRadius: 21, backgroundColor: '#E8E4D9', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#D4DAD5' },


  iconButtonText: { color: PRIMARY, fontSize: 22, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  timerOverlay: { position: 'absolute', top: 12, right: 12, zIndex: 20, gap: 6, width: 150 },


  timerWidget: { backgroundColor: '#2B3A2E', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7, opacity: 0.92 },


  timerTime: { color: '#FFFFFF', fontSize: 16, fontWeight: '900' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  timerTitle: { color: '#A8B5AA', fontSize: 10, fontWeight: '700', marginTop: 1 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.2},





  emptyCard: { backgroundColor: CARD, borderRadius: 12, padding: 24, alignItems: 'center', borderWidth: 1, borderColor: BORDER },


  emptyText: { fontSize: 16, fontWeight: '700', color: BLACK, marginBottom: 6 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  emptyHint: { fontSize: 13, color: GRAY, textAlign: 'center', lineHeight: 18 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  secondaryButton: { marginTop: 14, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, backgroundColor: '#E8E4D9' },


  secondaryButtonText: { color: PRIMARY, fontWeight: '700' },





  headerCard: { flexDirection: 'row', backgroundColor: CARD, borderRadius: 12, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: BORDER },


  headerStat: { flex: 1, alignItems: 'center' },


  headerStatNum: { fontSize: 22, fontWeight: '900', color: BLACK , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  headerStatNumTotal: { color: BLUE },


  headerStatLabel: { fontSize: 11, color: GRAY, marginTop: 2 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  headerDivider: { width: 1, backgroundColor: BORDER },





  strategyCard: { backgroundColor: '#E8E4D9', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: '#D4DAD5', marginBottom: 14 },


  strategyTitle: { fontSize: 15, fontWeight: '800', color: PRIMARY, marginBottom: 4, textTransform: 'capitalize' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3},


  strategyText: { fontSize: 13, color: '#4A5C4D', lineHeight: 18 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  errorText: { color: '#C8553D', textAlign: 'center', marginBottom: 10, fontWeight: '600' },





  sectionTitle: { fontSize: 17, fontWeight: '800', color: BLACK, marginTop: 8, marginBottom: 10 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.34},


  sessionList: { gap: 8, marginBottom: 10 },


  sessionCard: { backgroundColor: CARD, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: BORDER },


  sessionTop: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },


  sessionDate: { fontSize: 12, color: GRAY, fontWeight: '700', marginBottom: 2 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  sessionTitle: { fontSize: 16, color: BLACK, fontWeight: '900' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.32},


  sessionBadge: { alignSelf: 'flex-start', backgroundColor: '#E8E4D9', borderRadius: 9, paddingHorizontal: 10, paddingVertical: 5, alignItems: 'center' },


  sessionBadgeText: { color: PRIMARY, fontWeight: '800', fontSize: 12 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  sessionBadgeLabel: { color: PRIMARY, fontWeight: '700', fontSize: 10, marginTop: 1 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  sessionSub: { marginTop: 8, color: GRAY, fontSize: 12 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },


  chip: { backgroundColor: '#F0EEE7', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 5 },


  chipText: { color: '#374151', fontSize: 12, fontWeight: '600' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  productsToggle: { marginTop: 10, borderRadius: 10, borderWidth: 1, borderColor: '#D4DAD5', backgroundColor: '#F0EEE7', paddingHorizontal: 12, paddingVertical: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },


  productsToggleText: { color: PRIMARY, fontSize: 13, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  productsToggleIcon: { color: PRIMARY, fontSize: 16, fontWeight: '900' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  productsBox: { marginTop: 8, gap: 8 },


  productsModule: { borderRadius: 10, borderWidth: 1, borderColor: BORDER, padding: 10, backgroundColor: '#FAFAF7' },


  productsModuleTitle: { color: BLACK, fontSize: 13, fontWeight: '900', marginBottom: 4 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.26},


  productsModuleText: { color: GRAY, fontSize: 12, lineHeight: 17 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},





  stepGroup: { marginBottom: 8 },


  stepGroupTitle: { color: PRIMARY, fontSize: 14, fontWeight: '800', marginBottom: 8 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.28},


  stepCard: { flexDirection: 'row', gap: 8, marginBottom: 8, alignItems: 'flex-start' },


  stepCardDone: { opacity: 0.6 },


  stepIndex: { width: 30, height: 30, borderRadius: 15, backgroundColor: PRIMARY, alignItems: 'center', justifyContent: 'center', marginTop: 6 },


  stepIndexText: { color: '#FFFFFF', fontWeight: '900', fontSize: 12 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  stepCheck: { width: 28, height: 28, borderRadius: 8, backgroundColor: '#FAFAF7', borderWidth: 2, borderColor: PRIMARY, alignItems: 'center', justifyContent: 'center', marginTop: 7 },


  stepCheckDone: { backgroundColor: PRIMARY },


  stepCheckText: { color: PRIMARY, fontWeight: '900', fontSize: 15 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  stepCheckTextDone: { color: '#FFFFFF' },


  stepBody: { flex: 1, backgroundColor: CARD, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: BORDER },


  stepTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, gap: 8 },


  stepTitle: { fontSize: 15, fontWeight: '800', color: BLACK, flex: 1 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3},


  stepTitleDone: { color: GRAY },


  timeBadge: { backgroundColor: '#F0EEE7', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },


  timeBadgeParallel: { backgroundColor: PRIMARY },


  timeBadgeText: { fontSize: 12, fontWeight: '700', color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  timeBadgeTextParallel: { color: '#FFFFFF' },


  taskRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginBottom: 4 },


  taskDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: '#4A5C4D', marginTop: 6 },


  taskText: { fontSize: 13, color: GRAY, flex: 1, lineHeight: 18 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},





  moduleList: { gap: 8, marginBottom: 12 },


  moduleCard: { backgroundColor: CARD, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: BORDER },


  moduleTop: { flexDirection: 'row', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' },


  moduleTitle: { flex: 1, color: BLACK, fontSize: 15, fontWeight: '900' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3},


  modulePortions: { color: PRIMARY, fontWeight: '900', fontSize: 13 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  moduleType: { color: BLUE, fontSize: 12, fontWeight: '700', marginTop: 5 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  moduleNote: { color: GRAY, fontSize: 13, lineHeight: 18, marginTop: 5 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  moduleMeals: { color: '#4B5563', fontSize: 12, marginTop: 8, lineHeight: 17 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingList: { gap: 8, marginBottom: 12 },


  packingCard: { backgroundColor: CARD, borderRadius: 12, borderWidth: 1, borderColor: BORDER, padding: 12, flexDirection: 'row', gap: 10, alignItems: 'flex-start' },


  packingCardDone: { backgroundColor: '#E8E4D9', borderColor: '#D4DAD5', opacity: 0.78 },


  packingCheck: { width: 28, height: 28, borderRadius: 8, backgroundColor: '#FAFAF7', borderWidth: 2, borderColor: PRIMARY, alignItems: 'center', justifyContent: 'center', marginTop: 2 },


  packingCheckDone: { backgroundColor: PRIMARY },


  packingCheckText: { color: PRIMARY, fontWeight: '900', fontSize: 15 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingCheckTextDone: { color: '#FFFFFF' },


  packingBody: { flex: 1, minWidth: 0 },


  packingButtonText: { color: BLACK, fontSize: 14, fontWeight: '800', lineHeight: 19 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingButtonTextDone: { color: PRIMARY },


  packingMeta: { color: GRAY, fontSize: 12, fontWeight: '700', marginTop: 4 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},





  principlesCard: { backgroundColor: CARD, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: BORDER, marginTop: 4, marginBottom: 12 },


  principlesTitle: { color: BLACK, fontWeight: '900', fontSize: 15, marginBottom: 8 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3},


  principleRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginBottom: 5 },


  principleText: { flex: 1, color: GRAY, fontSize: 13, lineHeight: 18 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},





  outlineButton: { borderWidth: 1, borderColor: PRIMARY, borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 4 },


  outlineButtonText: { color: PRIMARY, fontWeight: '800', fontSize: 14 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingModuleCard: { backgroundColor: CARD, borderRadius: 12, borderWidth: 1, borderColor: BORDER, padding: 14, marginBottom: 10 },


  packingModuleCardDone: { opacity: 0.7 },


  packingModuleHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },


  packingModuleTitle: { fontSize: 15, fontWeight: '900', color: BLACK, flex: 1 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3},


  packingModuleNote: { fontSize: 12, color: GRAY, lineHeight: 16, marginBottom: 10 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingWarnBadge: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#F9F6EE', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 5, marginBottom: 10, alignSelf: 'flex-start' },


  packingWarnText: { fontSize: 11, color: '#C9A14B', fontWeight: '600' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingLocGroup: { borderTopWidth: 1, borderTopColor: BORDER, marginTop: 10, paddingTop: 10 },


  packingLocHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },


  packingLocName: { fontSize: 13, fontWeight: '800', flex: 1 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingLocCount: { fontSize: 11, color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingContainer: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#F0EEE7' },


  packingContainerDone: { opacity: 0.5 },


  packingLabel: { width: 38, height: 38, borderRadius: 8, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FAFAF7' },


  packingLabelText: { fontSize: 11, fontWeight: '900' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingContainerInfo: { flex: 1, minWidth: 0 },


  packingMealName: { fontSize: 13, fontWeight: '700', color: BLACK , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingMealDate: { fontSize: 11, color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingGrams: { fontSize: 12, fontWeight: '700', color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 10, borderWidth: 1.5, borderRadius: 10, paddingVertical: 10 },


  packingBtnText: { fontSize: 13, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingDoneRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 8 },


  packingDoneText: { fontSize: 12, color: '#5A7A5C', fontWeight: '600', flex: 1 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  packingUndoBtn: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, borderWidth: 1, borderColor: '#D4DAD5' },


  packingUndoText: { fontSize: 11, color: '#6E7E70', fontWeight: '600' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},


  sessionPackingWrap: { marginTop: 14, backgroundColor: '#F9F6EE', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#D4DAD5' },


  sessionPackingHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },


  sessionPackingHeader: { fontSize: 13, fontWeight: '800', color: PRIMARY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},

  packingContainerList: { gap: 4, marginTop: 6, marginBottom: 2 },
  packingContainerRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  packingLabelPill: { backgroundColor: '#E8E4D9', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3, minWidth: 44, alignItems: 'center' },
  packingLabelPillText: { fontSize: 11, fontWeight: '900', color: PRIMARY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  packingGramsBig: { fontSize: 15, fontWeight: '800', color: BLACK, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  packingDateTag: { fontSize: 11, color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  noPlanCard: { backgroundColor: CARD, borderRadius: 16, borderWidth: 1, borderColor: '#D4DAD5', padding: 24, alignItems: 'center', marginTop: 8 },
  noPlanIconWrap: { width: 64, height: 64, borderRadius: 32, backgroundColor: '#E8E4D9', alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  noPlanTitle: { fontSize: 18, fontWeight: '800', color: BLACK, marginBottom: 8, textAlign: 'center', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.36 },
  noPlanHint: { fontSize: 14, color: GRAY, lineHeight: 20, textAlign: 'center', marginBottom: 20, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  noPlanBtn: { backgroundColor: PRIMARY, borderRadius: 12, paddingHorizontal: 24, paddingVertical: 13 },
  noPlanBtnText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
});


