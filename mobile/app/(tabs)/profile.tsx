import { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect } from 'expo-router';
import { profileApi, ProfileCreateRequest, ProfileResponse } from '@/api/profile';
import { useAuthStore } from '@/store/authStore';
import { usePlanStore } from '@/store/planStore';

const PRIMARY = '#1A7340';
const BLUE = '#2563EB';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';
const BORDER = '#E5E7EB';
const DANGER = '#DC2626';

const GOALS = [
  { id: 'loss', label: 'Похудение' },
  { id: 'maintain', label: 'Поддержание' },
  { id: 'gain', label: 'Набор массы' },
  { id: 'recomp', label: 'Рекомпозиция' },
];

const SEX_OPTIONS = [
  { id: 'male', label: 'Мужчина' },
  { id: 'female', label: 'Женщина' },
];

const ACTIVITY_OPTIONS = [
  { id: 'sedentary', label: 'Офис, без спорта' },
  { id: 'light', label: '1-3 тренировки/нед' },
  { id: 'moderate', label: '3-5 тренировок/нед' },
  { id: 'active', label: '6-7 тренировок/нед' },
  { id: 'very_active', label: 'Физический труд + спорт' },
];

const DIET_OPTIONS = [
  { id: '', label: 'Без ограничений' },
  { id: 'balanced', label: 'Сбалансированное' },
  { id: 'low_carb', label: 'Меньше углеводов' },
  { id: 'high_protein', label: 'Больше белка' },
  { id: 'vegetarian', label: 'Вегетарианское' },
];

const COOKING_OPTIONS = [
  { id: 'daily', label: 'Каждый день' },
  { id: 'twice_a_week', label: '2 раза в неделю' },
  { id: 'once_a_week', label: '1 раз в неделю' },
];

const WEEK_DAY_LABELS: Record<string, string> = {
  mon: 'Пн',
  tue: 'Вт',
  wed: 'Ср',
  thu: 'Чт',
  fri: 'Пт',
  sat: 'Сб',
  sun: 'Вс',
};

const DEFAULT_SCHEDULE = {
  breakfast: '08:00',
  lunch: '13:00',
  snack: '16:00',
  dinner: '19:00',
};

const MEALS = [
  { key: 'breakfast', label: 'Завтрак', emoji: '🌅' },
  { key: 'lunch', label: 'Обед', emoji: '☀️' },
  { key: 'snack', label: 'Перекус', emoji: '🍎' },
  { key: 'dinner', label: 'Ужин', emoji: '🌙' },
] as const;

const CHECKBOXES = {
  allergies: ['Лактоза', 'Глютен', 'Орехи', 'Яйца', 'Морепродукты', 'Соя'],
  disliked_foods: ['Рыба', 'Говядина', 'Курица', 'Творог', 'Гречка', 'Овсянка'],
  kitchen_equipment: ['Духовка', 'Плита', 'Микроволновка', 'Мультиварка', 'Блендер', 'Гриль'],
};

type ProfileForm = {
  sex: string;
  age: string;
  height_cm: string;
  weight_kg: string;
  activity_level: string;
  goal: string;
  allergies: string[];
  disliked_foods: string[];
  diet_type: string;
  budget_rub_week: string;
  cooking_frequency: string;
  family_size: string;
  kitchen_equipment: string[];
  eating_schedule: Record<string, string>;
  planned_deviations_text: string;
  flexibility_pct: string;
};

const emptyForm: ProfileForm = {
  sex: 'male',
  age: '30',
  height_cm: '175',
  weight_kg: '80',
  activity_level: 'moderate',
  goal: 'maintain',
  allergies: [],
  disliked_foods: [],
  diet_type: '',
  budget_rub_week: '',
  cooking_frequency: 'twice_a_week',
  family_size: '1',
  kitchen_equipment: [],
  eating_schedule: DEFAULT_SCHEDULE,
  planned_deviations_text: '',
  flexibility_pct: '10',
};

function labelOf(options: Array<{ id: string; label: string }>, value?: string | null) {
  return options.find((item) => item.id === value)?.label ?? 'Не задано';
}

function numberText(value: number | null | undefined, fallback = '') {
  return value === null || value === undefined ? fallback : String(value);
}

function formatList(value?: string[] | null, fallback = 'Не задано') {
  return value?.length ? value.join(', ') : fallback;
}

function avatarInitial(name?: string | null) {
  const trimmed = name?.trim();
  return trimmed ? trimmed[0].toUpperCase() : 'К';
}

function scheduleMeals(profile: ProfileResponse) {
  const meals = profile.eating_schedule?.meals;
  if (Array.isArray(meals) && meals.length > 0) {
    return meals.map((meal: any, index: number) => ({
      key: meal.id || `meal_${index + 1}`,
      label: meal.name || `Прием ${index + 1}`,
      time: meal.time || profile.eating_schedule?.[meal.id] || '12:00',
    }));
  }

  return MEALS.map((meal) => ({
    key: meal.key,
    label: meal.label,
    time: profile.eating_schedule?.[meal.key] ?? DEFAULT_SCHEDULE[meal.key],
  }));
}

function measurementsText(profile: ProfileResponse) {
  const measurements = profile.measurements ?? {};
  const rows = [
    measurements.chest_cm ? `грудь ${measurements.chest_cm} см` : '',
    measurements.waist_cm ? `талия ${measurements.waist_cm} см` : '',
    measurements.hips_cm ? `бедра ${measurements.hips_cm} см` : '',
  ].filter(Boolean);
  return rows.length ? rows.join(', ') : 'Не заданы';
}

function cookingTimeText(profile: ProfileResponse) {
  const budget = profile.cooking_time_budget ?? {};
  const minutes = budget.minutes;
  const period = budget.period === 'day' ? 'в день' : 'в неделю';
  return minutes ? `${minutes} мин ${period}` : 'Не задано';
}

function profileToForm(profile: ProfileResponse): ProfileForm {
  return {
    sex: profile.sex ?? 'male',
    age: numberText(profile.age, '30'),
    height_cm: numberText(profile.height_cm, '175'),
    weight_kg: numberText(profile.weight_kg, '80'),
    activity_level: profile.activity_level ?? 'moderate',
    goal: profile.goal ?? 'maintain',
    allergies: profile.allergies ?? [],
    disliked_foods: profile.disliked_foods ?? [],
    diet_type: profile.diet_type ?? '',
    budget_rub_week: numberText(profile.budget_rub_week),
    cooking_frequency: profile.cooking_frequency ?? 'twice_a_week',
    family_size: numberText(profile.family_size, '1'),
    kitchen_equipment: profile.kitchen_equipment ?? [],
    eating_schedule: { ...DEFAULT_SCHEDULE, ...(profile.eating_schedule ?? {}) },
    planned_deviations_text: (profile.planned_deviations ?? [])
      .map((item: any) => item.description)
      .filter(Boolean)
      .join('\n'),
    flexibility_pct: numberText(profile.flexibility_pct, '10'),
  };
}

function parseNumber(value: string, fallback: number) {
  const normalized = value.replace(',', '.').trim();
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseOptionalInt(value: string) {
  const parsed = parseInt(value.trim(), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function buildPayload(form: ProfileForm): Partial<ProfileCreateRequest> {
  return {
    sex: form.sex,
    age: Math.round(parseNumber(form.age, 30)),
    height_cm: parseNumber(form.height_cm, 175),
    weight_kg: parseNumber(form.weight_kg, 80),
    activity_level: form.activity_level,
    goal: form.goal,
    allergies: form.allergies,
    disliked_foods: form.disliked_foods,
    diet_type: form.diet_type || null,
    budget_rub_week: parseOptionalInt(form.budget_rub_week),
    cooking_frequency: form.cooking_frequency,
    family_size: Math.max(1, Math.round(parseNumber(form.family_size, 1))),
    kitchen_equipment: form.kitchen_equipment,
    eating_schedule: form.eating_schedule,
    planned_deviations: form.planned_deviations_text
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((description) => ({
        type: 'user_input',
        description,
        day_of_week: null,
        kcal_extra: 0,
      })),
    flexibility_pct: Math.max(0, Math.min(50, Math.round(parseNumber(form.flexibility_pct, 10)))),
  };
}

function ChipGroup({
  options,
  value,
  onChange,
}: {
  options: Array<{ id: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <View style={s.chipRow}>
      {options.map((option) => {
        const active = value === option.id;
        return (
          <TouchableOpacity
            key={option.id}
            style={[s.chip, active && s.chipActive]}
            onPress={() => onChange(option.id)}
            activeOpacity={0.75}
          >
            <Text style={[s.chipText, active && s.chipTextActive]}>{option.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

function MultiChipGroup({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const toggle = (item: string) => {
    onChange(value.includes(item) ? value.filter((current) => current !== item) : [...value, item]);
  };

  return (
    <View style={s.chipRow}>
      {options.map((option) => {
        const active = value.includes(option);
        return (
          <TouchableOpacity
            key={option}
            style={[s.chip, active && s.chipActive]}
            onPress={() => toggle(option)}
            activeOpacity={0.75}
          >
            <Text style={[s.chipText, active && s.chipTextActive]}>{option}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

function Field({
  label,
  value,
  onChangeText,
  unit,
  multiline,
  keyboardType = 'numeric',
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  unit?: string;
  multiline?: boolean;
  keyboardType?: 'default' | 'numeric';
}) {
  return (
    <View style={multiline ? s.fieldBlock : s.fieldRow}>
      <Text style={s.fieldLabel}>{label}</Text>
      <View style={[s.inputWrap, multiline && s.inputWrapMultiline]}>
        <TextInput
          style={[s.input, multiline && s.inputMultiline]}
          value={value}
          onChangeText={onChangeText}
          keyboardType={multiline ? 'default' : keyboardType}
          multiline={multiline}
          placeholderTextColor={GRAY}
        />
        {!!unit && <Text style={s.unit}>{unit}</Text>}
      </View>
    </View>
  );
}

function showConfirm(title: string, message: string, onConfirm: () => void) {
  if (Platform.OS === 'web') {
    if (window.confirm(`${title}\n\n${message}`)) onConfirm();
    return;
  }
  Alert.alert(title, message, [
    { text: 'Отмена', style: 'cancel' },
    { text: 'Продолжить', style: 'destructive', onPress: onConfirm },
  ]);
}

export default function ProfileScreen() {
  const logout = useAuthStore((state) => state.logout);
  const clearPlan = usePlanStore((state) => state.clearPlan);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [form, setForm] = useState<ProfileForm>(emptyForm);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await profileApi.get();
      setProfile(data);
      setForm(profileToForm(data));
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Не удалось загрузить профиль');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadProfile();
    }, [loadProfile]),
  );

  const stats = useMemo(() => {
    if (!profile) return [];
    return [
      { label: 'Текущий вес', value: `${profile.weight_kg ?? 0} кг` },
      { label: 'Цель', value: labelOf(GOALS, profile.goal) },
      { label: 'Бюджет', value: profile.budget_rub_week ? `${profile.budget_rub_week} ₽/нед` : 'Не задан' },
      { label: 'Гибкость', value: `${profile.flexibility_pct ?? 10}%` },
    ];
  }, [profile]);

  const visibleMeals = useMemo(() => profile ? scheduleMeals(profile) : [], [profile]);

  const profileRows = useMemo(() => {
    if (!profile) return [];
    const rows = [
      { label: 'Пол', value: labelOf(SEX_OPTIONS, profile.sex) },
      { label: 'Возраст', value: profile.age ? `${profile.age} лет` : 'Не задано' },
      { label: 'Рост', value: profile.height_cm ? `${profile.height_cm} см` : 'Не задано' },
      { label: 'Активность', value: labelOf(ACTIVITY_OPTIONS, profile.activity_level) },
      { label: 'Тренировки', value: profile.training_days?.length ? profile.training_days.map((day) => WEEK_DAY_LABELS[day] ?? day).join(', ') : 'Не заданы' },
      { label: 'Спорт', value: formatList(profile.sport_types) },
      { label: 'Замеры', value: measurementsText(profile) },
      { label: 'Готовка', value: labelOf(COOKING_OPTIONS, profile.cooking_frequency) },
      { label: 'Время на готовку', value: cookingTimeText(profile) },
      { label: 'Семья', value: `${profile.family_size ?? 1} чел.` },
      { label: 'Техника', value: formatList(profile.kitchen_equipment) },
      { label: 'Нелюбимые продукты', value: formatList(profile.disliked_foods, 'Нет') },
      { label: 'Аллергии', value: formatList(profile.allergies, 'Нет') },
    ];
    if (profile.diet_type) {
      rows.splice(7, 0, { label: 'Тип питания', value: labelOf(DIET_OPTIONS, profile.diet_type) });
    }
    return rows;
  }, [profile]);

  const saveProfile = async () => {
    setSaving(true);
    setError('');
    try {
      const updated = await profileApi.update(buildPayload(form));
      setProfile(updated);
      setForm(profileToForm(updated));
      setEditing(false);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Не удалось сохранить профиль');
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    showConfirm('Выйти из профиля?', 'Текущий вход будет сброшен на этом устройстве. После выхода можно войти заново или создать новый аккаунт.', async () => {
      await clearPlan();
      await logout();
      router.replace('/onboarding/step1');
    });
  };

  if (loading) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.center}>
          <ActivityIndicator color={PRIMARY} />
          <Text style={s.centerText}>Загружаем профиль</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!profile) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.center}>
          <Text style={s.errorText}>{error || 'Профиль не найден'}</Text>
          <TouchableOpacity style={s.primaryBtn} onPress={loadProfile}>
            <Text style={s.primaryBtnText}>Повторить</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.secondaryBtn} onPress={handleLogout}>
            <Text style={s.secondaryBtnText}>Выйти из профиля</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          <View style={s.avatarSection}>
            <View style={s.avatar}>
              <Text style={s.avatarText}>{avatarInitial(profile.name)}</Text>
            </View>
            <View style={s.headerText}>
              <Text style={s.userName}>{profile.name || 'Профиль КБЖУЙ'}</Text>
              <View style={s.goalBadge}>
                <Text style={s.goalBadgeText}>🎯 {labelOf(GOALS, profile.goal)}</Text>
              </View>
            </View>
          </View>

          {!editing && (
            <>
              <View style={s.statsGrid}>
                {stats.map((stat) => (
                  <View key={stat.label} style={s.statCard}>
                    <Text style={s.statValue}>{stat.value}</Text>
                    <Text style={s.statLabel}>{stat.label}</Text>
                  </View>
                ))}
              </View>

              <Text style={s.sectionTitle}>КБЖУ-цели в день</Text>
              <View style={s.kbzhuGrid}>
                {[
                  { label: 'Калории', value: profile.target_kcal ?? 0, unit: 'ккал', color: PRIMARY },
                  { label: 'Белки', value: profile.target_protein_g ?? 0, unit: 'г', color: '#3B82F6' },
                  { label: 'Жиры', value: profile.target_fat_g ?? 0, unit: 'г', color: '#F59E0B' },
                  { label: 'Углев.', value: profile.target_carbs_g ?? 0, unit: 'г', color: '#8B5CF6' },
                ].map((item) => (
                  <View key={item.label} style={s.kbzhuCard}>
                    <View style={[s.kbzhuStripe, { backgroundColor: item.color }]} />
                    <Text style={[s.kbzhuValue, { color: item.color }]}>{item.value}</Text>
                    <Text style={s.kbzhuUnit}>{item.unit}</Text>
                    <Text style={s.kbzhuLabel}>{item.label}</Text>
                  </View>
                ))}
              </View>

              <Text style={s.sectionTitle}>Расписание</Text>
              <View style={s.card}>
                {visibleMeals.map((meal, idx) => (
                  <View key={meal.key} style={[s.scheduleRow, idx < visibleMeals.length - 1 && s.scheduleRowBorder]}>
                    <Text style={s.scheduleEmoji}>🍽</Text>
                    <Text style={s.scheduleName}>{meal.label}</Text>
                    <View style={s.scheduleTimeBadge}>
                      <Text style={s.scheduleTime}>{meal.time}</Text>
                    </View>
                  </View>
                ))}
              </View>

              <Text style={s.sectionTitle}>Плановые отклонения</Text>
              {(profile.planned_deviations?.length ?? 0) > 0 ? (
                profile.planned_deviations?.map((dev: any, index) => (
                  <View key={`${dev.description}-${index}`} style={s.deviationCard}>
                    <Text style={s.deviationEmoji}>🍽</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={s.deviationName}>{dev.description}</Text>
                      <Text style={s.deviationDay}>Будет учтено при AI-генерации меню</Text>
                    </View>
                  </View>
                ))
              ) : (
                <View style={s.emptyBand}>
                  <Text style={s.emptyBandText}>Отклонения не заданы</Text>
                </View>
              )}

              <TouchableOpacity style={s.settingsBtn} onPress={() => router.push('/profile-settings' as any)} activeOpacity={0.75}>
                <Text style={s.settingsBtnText}>⚙️ Настройки профиля</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.logoutBtn} onPress={handleLogout} activeOpacity={0.75}>
                <Text style={s.logoutBtnText}>Выйти из профиля</Text>
              </TouchableOpacity>
            </>
          )}

          {editing && (
            <>
              <Text style={s.sectionTitle}>Цель</Text>
              <ChipGroup options={GOALS} value={form.goal} onChange={(goal) => setForm((prev) => ({ ...prev, goal }))} />

              <Text style={s.sectionTitle}>Пол</Text>
              <ChipGroup options={SEX_OPTIONS} value={form.sex} onChange={(sex) => setForm((prev) => ({ ...prev, sex }))} />

              <View style={s.card}>
                <Field label="Возраст" value={form.age} onChangeText={(age) => setForm((prev) => ({ ...prev, age }))} unit="лет" />
                <Field label="Рост" value={form.height_cm} onChangeText={(height_cm) => setForm((prev) => ({ ...prev, height_cm }))} unit="см" />
                <Field label="Вес" value={form.weight_kg} onChangeText={(weight_kg) => setForm((prev) => ({ ...prev, weight_kg }))} unit="кг" />
                <Field label="Семья" value={form.family_size} onChangeText={(family_size) => setForm((prev) => ({ ...prev, family_size }))} unit="чел." />
              </View>

              <Text style={s.sectionTitle}>Активность</Text>
              <ChipGroup options={ACTIVITY_OPTIONS} value={form.activity_level} onChange={(activity_level) => setForm((prev) => ({ ...prev, activity_level }))} />

              <Text style={s.sectionTitle}>Тип питания</Text>
              <ChipGroup options={DIET_OPTIONS} value={form.diet_type} onChange={(diet_type) => setForm((prev) => ({ ...prev, diet_type }))} />

              <Text style={s.sectionTitle}>Готовка</Text>
              <ChipGroup options={COOKING_OPTIONS} value={form.cooking_frequency} onChange={(cooking_frequency) => setForm((prev) => ({ ...prev, cooking_frequency }))} />

              <Text style={s.sectionTitle}>Расписание</Text>
              <View style={s.card}>
                {MEALS.map((meal) => (
                  <Field
                    key={meal.key}
                    label={meal.label}
                    value={form.eating_schedule[meal.key] ?? DEFAULT_SCHEDULE[meal.key]}
                    keyboardType="default"
                    onChangeText={(time) => setForm((prev) => ({
                      ...prev,
                      eating_schedule: { ...prev.eating_schedule, [meal.key]: time },
                    }))}
                  />
                ))}
              </View>

              <View style={s.card}>
                <Field label="Бюджет" value={form.budget_rub_week} onChangeText={(budget_rub_week) => setForm((prev) => ({ ...prev, budget_rub_week }))} unit="₽/нед" />
                <Field label="Гибкость" value={form.flexibility_pct} onChangeText={(flexibility_pct) => setForm((prev) => ({ ...prev, flexibility_pct }))} unit="%" />
              </View>

              <Text style={s.sectionTitle}>Аллергии</Text>
              <MultiChipGroup options={CHECKBOXES.allergies} value={form.allergies} onChange={(allergies) => setForm((prev) => ({ ...prev, allergies }))} />

              <Text style={s.sectionTitle}>Нелюбимые продукты</Text>
              <MultiChipGroup options={CHECKBOXES.disliked_foods} value={form.disliked_foods} onChange={(disliked_foods) => setForm((prev) => ({ ...prev, disliked_foods }))} />

              <Text style={s.sectionTitle}>Техника на кухне</Text>
              <MultiChipGroup options={CHECKBOXES.kitchen_equipment} value={form.kitchen_equipment} onChange={(kitchen_equipment) => setForm((prev) => ({ ...prev, kitchen_equipment }))} />

              <Text style={s.sectionTitle}>Плановые отклонения</Text>
              <Field
                label="Каждое с новой строки"
                value={form.planned_deviations_text}
                onChangeText={(planned_deviations_text) => setForm((prev) => ({ ...prev, planned_deviations_text }))}
                multiline
              />

              {!!error && <Text style={s.errorText}>{error}</Text>}

              <TouchableOpacity style={s.primaryBtn} onPress={saveProfile} disabled={saving} activeOpacity={0.8}>
                {saving ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryBtnText}>Сохранить профиль</Text>}
              </TouchableOpacity>
              <TouchableOpacity style={s.secondaryBtn} onPress={() => setForm(emptyForm)} activeOpacity={0.75}>
                <Text style={s.secondaryBtnText}>Сбросить форму</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={s.secondaryBtn}
                onPress={() => {
                  setForm(profileToForm(profile));
                  setEditing(false);
                }}
                activeOpacity={0.75}
              >
                <Text style={s.secondaryBtnText}>Отмена</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.logoutBtn} onPress={handleLogout} activeOpacity={0.75}>
                <Text style={s.logoutBtnText}>Выйти из профиля</Text>
              </TouchableOpacity>
            </>
          )}

          <View style={{ height: 24 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 12 },
  centerText: { fontSize: 14, color: GRAY },

  avatarSection: { flexDirection: 'row', alignItems: 'center', gap: 14, marginBottom: 16 },
  avatar: { width: 60, height: 60, borderRadius: 30, backgroundColor: PRIMARY, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 26, fontWeight: '800', color: '#FFF' },
  headerText: { flex: 1 },
  userName: { fontSize: 20, fontWeight: '800', color: BLACK },
  goalBadge: { marginTop: 3, backgroundColor: '#D1FAE5', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3, alignSelf: 'flex-start' },
  goalBadgeText: { fontSize: 12, fontWeight: '600', color: PRIMARY },

  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  statCard: { flex: 1, minWidth: '45%', backgroundColor: CARD, borderRadius: 8, padding: 14, boxShadow: '0 1px 6px rgba(0,0,0,0.04)' },
  statValue: { fontSize: 18, fontWeight: '800', color: BLACK },
  statLabel: { fontSize: 11, color: GRAY, marginTop: 2 },

  sectionTitle: { fontSize: 15, fontWeight: '700', color: BLACK, marginBottom: 8, marginTop: 8 },

  kbzhuGrid: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  kbzhuCard: { flex: 1, backgroundColor: CARD, borderRadius: 8, padding: 10, alignItems: 'center', overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.03)' },
  kbzhuStripe: { position: 'absolute', top: 0, left: 0, right: 0, height: 3 },
  kbzhuValue: { fontSize: 18, fontWeight: '800', marginTop: 6 },
  kbzhuUnit: { fontSize: 10, color: GRAY, marginTop: -2 },
  kbzhuLabel: { fontSize: 10, color: GRAY, marginTop: 4, textAlign: 'center' },

  card: { backgroundColor: CARD, borderRadius: 8, padding: 4, marginBottom: 16, boxShadow: '0 1px 6px rgba(0,0,0,0.04)' },
  scheduleRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 11, paddingHorizontal: 12 },
  scheduleRowBorder: { borderBottomWidth: 1, borderBottomColor: '#F3F4F6' },
  scheduleEmoji: { fontSize: 18 },
  scheduleName: { flex: 1, fontSize: 14, fontWeight: '600', color: BLACK },
  scheduleTimeBadge: { backgroundColor: '#D1FAE5', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4 },
  scheduleTime: { fontSize: 14, fontWeight: '700', color: PRIMARY },

  infoGrid: { backgroundColor: CARD, borderRadius: 8, padding: 4, marginBottom: 16 },
  infoRow: { flexDirection: 'row', gap: 12, justifyContent: 'space-between', paddingVertical: 12, paddingHorizontal: 12, borderBottomWidth: 1, borderBottomColor: '#F3F4F6' },
  infoLabel: { fontSize: 13, color: GRAY },
  infoValue: { flex: 1, fontSize: 13, color: BLACK, fontWeight: '600', textAlign: 'right' },

  deviationCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFFBEB', borderRadius: 8, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: '#FDE68A' },
  deviationEmoji: { fontSize: 22 },
  deviationName: { fontSize: 14, fontWeight: '700', color: '#92400E' },
  deviationDay: { fontSize: 12, color: GRAY, marginTop: 1 },
  emptyBand: { backgroundColor: CARD, borderRadius: 8, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: BORDER },
  emptyBandText: { color: GRAY, fontSize: 13, textAlign: 'center' },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  chip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, backgroundColor: CARD, borderWidth: 1.5, borderColor: BORDER },
  chipActive: { backgroundColor: '#F0FDF4', borderColor: PRIMARY },
  chipText: { fontSize: 13, fontWeight: '600', color: GRAY },
  chipTextActive: { color: PRIMARY },

  fieldRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 12, paddingHorizontal: 12, borderBottomWidth: 1, borderBottomColor: '#F3F4F6' },
  fieldBlock: { backgroundColor: CARD, borderRadius: 8, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: BORDER },
  fieldLabel: { fontSize: 14, color: BLACK, flex: 1 },
  inputWrap: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  inputWrapMultiline: { alignItems: 'stretch', marginTop: 10 },
  input: { fontSize: 16, fontWeight: '700', color: PRIMARY, textAlign: 'right', minWidth: 70 },
  inputMultiline: { minHeight: 96, textAlignVertical: 'top', textAlign: 'left', color: BLACK, fontWeight: '500', backgroundColor: '#F9FAFB', borderRadius: 8, padding: 10 },
  unit: { fontSize: 13, color: GRAY },

  settingsBtn: { backgroundColor: CARD, borderRadius: 8, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: BORDER, marginTop: 8 },
  settingsBtnText: { fontSize: 14, fontWeight: '700', color: GRAY },
  primaryBtn: { backgroundColor: PRIMARY, borderRadius: 8, paddingVertical: 15, alignItems: 'center', marginTop: 8 },
  primaryBtnText: { color: '#FFF', fontSize: 15, fontWeight: '800' },
  secondaryBtn: { backgroundColor: CARD, borderRadius: 8, paddingVertical: 14, alignItems: 'center', marginTop: 8, borderWidth: 1, borderColor: BORDER },
  secondaryBtnText: { color: GRAY, fontSize: 14, fontWeight: '700' },
  logoutBtn: { backgroundColor: '#FEF2F2', borderRadius: 8, paddingVertical: 14, alignItems: 'center', marginTop: 8, borderWidth: 1, borderColor: '#FECACA' },
  logoutBtnText: { color: DANGER, fontSize: 14, fontWeight: '800' },
  errorText: { color: DANGER, fontSize: 13, textAlign: 'center', marginVertical: 10 },
});
