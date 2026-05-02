import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
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
import { router } from 'expo-router';
import { profileApi, ProfileCreateRequest, ProfileResponse } from '@/api/profile';
import { usePlanStore } from '@/store/planStore';
import { shouldInvalidatePlan } from '@/utils/profilePlanInvalidation';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';
const BORDER = '#D4DAD5';
const DANGER = '#C8553D';

const GOALS = [
  { id: 'loss', label: 'Похудение' },
  { id: 'maintain', label: 'Поддержание' },
  { id: 'gain', label: 'Набор массы' },
  { id: 'recomp', label: 'Рекомпозиция' },
];

const SEX_OPTIONS = [
  { id: 'female', label: 'Женщина' },
  { id: 'male', label: 'Мужчина' },
];

const ACTIVITY_OPTIONS = [
  { id: 'sedentary', label: 'Офис, без спорта' },
  { id: 'light', label: '1-3 тренировки/нед' },
  { id: 'moderate', label: '3-5 тренировок/нед' },
  { id: 'active', label: '6-7 тренировок/нед' },
  { id: 'very_active', label: 'Физический труд + спорт' },
];

const WEEK_DAYS = [
  { id: 'mon', label: 'Пн' },
  { id: 'tue', label: 'Вт' },
  { id: 'wed', label: 'Ср' },
  { id: 'thu', label: 'Чт' },
  { id: 'fri', label: 'Пт' },
  { id: 'sat', label: 'Сб' },
  { id: 'sun', label: 'Вс' },
];

const ALLERGY_OPTIONS = ['Лактоза', 'Глютен', 'Орехи', 'Яйца', 'Морепродукты', 'Соя'];
const EQUIPMENT_OPTIONS = ['Плита', 'Духовка', 'Микроволновка', 'Мультиварка', 'Блендер', 'Гриль'];
const COOKING_OPTIONS = [
  { id: 'daily', label: 'Каждый день' },
  { id: 'twice_a_week', label: '2 раза в неделю' },
  { id: 'once_a_week', label: '1 раз в неделю' },
];

type MealSlot = { id: string; name: string; time: string };

type ProfileForm = {
  name: string;
  sex: string;
  age: string;
  height_cm: string;
  weight_kg: string;
  activity_level: string;
  chest_cm: string;
  waist_cm: string;
  hips_cm: string;
  training_days: string[];
  sport_text: string;
  goal: string;
  allergies: string[];
  custom_allergies: string;
  disliked_foods: string;
  budget_rub_week: string;
  cooking_frequency: string;
  cook_minutes: string;
  cook_period: 'day' | 'week';
  family_size: string;
  kitchen_equipment: string[];
  meals: MealSlot[];
  planned_deviations_text: string;
  flexibility_pct: string;
};

const DEFAULT_MEALS: MealSlot[] = [
  { id: 'meal_1', name: 'Завтрак', time: '08:00' },
  { id: 'meal_2', name: 'Обед', time: '13:00' },
  { id: 'meal_3', name: 'Перекус', time: '16:00' },
  { id: 'meal_4', name: 'Ужин', time: '19:00' },
];

const defaultForm: ProfileForm = {
  name: '',
  sex: 'female',
  age: '30',
  height_cm: '170',
  weight_kg: '70',
  activity_level: 'moderate',
  chest_cm: '',
  waist_cm: '',
  hips_cm: '',
  training_days: [],
  sport_text: '',
  goal: 'maintain',
  allergies: [],
  custom_allergies: '',
  disliked_foods: '',
  budget_rub_week: '',
  cooking_frequency: 'twice_a_week',
  cook_minutes: '60',
  cook_period: 'week',
  family_size: '1',
  kitchen_equipment: [],
  meals: DEFAULT_MEALS,
  planned_deviations_text: '',
  flexibility_pct: '10',
};

function numberText(value: number | null | undefined, fallback = '') {
  return value === null || value === undefined ? fallback : String(value);
}

function parseNumber(value: string, fallback: number) {
  const parsed = Number(value.replace(',', '.').trim());
  return Number.isFinite(parsed) ? parsed : fallback;
}

function optionalInt(value: string) {
  const parsed = parseInt(value.trim(), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function optionalFloat(value: string) {
  const parsed = Number(value.replace(',', '.').trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function splitList(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function uniqList(value: string[]) {
  return Array.from(new Set(value.map((item) => item.trim()).filter(Boolean)));
}

function profileMeals(profile: ProfileResponse): MealSlot[] {
  const meals = profile.eating_schedule?.meals;
  if (Array.isArray(meals) && meals.length > 0) {
    return meals.map((meal: any, index: number) => ({
      id: meal.id || `meal_${index + 1}`,
      name: meal.name || `Прием ${index + 1}`,
      time: meal.time || profile.eating_schedule?.[meal.id] || '12:00',
    }));
  }

  return DEFAULT_MEALS.map((meal) => ({
    ...meal,
    time: profile.eating_schedule?.[meal.id] ?? meal.time,
  }));
}

function profileToForm(profile: ProfileResponse): ProfileForm {
  const allergies = profile.allergies ?? [];
  const selectedAllergies = allergies.filter((item) => ALLERGY_OPTIONS.includes(item));
  const customAllergies = allergies.filter((item) => !ALLERGY_OPTIONS.includes(item));
  const cookingTime = profile.cooking_time_budget ?? {};

  return {
    name: profile.name ?? '',
    sex: profile.sex ?? 'female',
    age: numberText(profile.age, '30'),
    height_cm: numberText(profile.height_cm, '170'),
    weight_kg: numberText(profile.weight_kg, '70'),
    activity_level: profile.activity_level ?? 'moderate',
    chest_cm: numberText(profile.measurements?.chest_cm),
    waist_cm: numberText(profile.measurements?.waist_cm),
    hips_cm: numberText(profile.measurements?.hips_cm),
    training_days: profile.training_days ?? [],
    sport_text: (profile.sport_types ?? []).join(', '),
    goal: profile.goal ?? 'maintain',
    allergies: selectedAllergies,
    custom_allergies: customAllergies.join(', '),
    disliked_foods: (profile.disliked_foods ?? []).join(', '),
    budget_rub_week: numberText(profile.budget_rub_week),
    cooking_frequency: profile.cooking_frequency ?? 'twice_a_week',
    cook_minutes: numberText(cookingTime.minutes as number | null | undefined, '60'),
    cook_period: cookingTime.period === 'day' ? 'day' : 'week',
    family_size: numberText(profile.family_size, '1'),
    kitchen_equipment: profile.kitchen_equipment ?? [],
    meals: profileMeals(profile),
    planned_deviations_text: (profile.planned_deviations ?? [])
      .map((item: any) => item.description)
      .filter(Boolean)
      .join('\n'),
    flexibility_pct: numberText(profile.flexibility_pct, '10'),
  };
}

function buildPayload(form: ProfileForm): Partial<ProfileCreateRequest> {
  const meals = form.meals.map((meal, index) => ({
    id: `meal_${index + 1}`,
    name: meal.name.trim() || `Прием ${index + 1}`,
    time: meal.time.trim() || '12:00',
  }));

  return {
    name: form.name.trim() || null,
    sex: form.sex,
    age: Math.round(parseNumber(form.age, 30)),
    height_cm: parseNumber(form.height_cm, 170),
    weight_kg: parseNumber(form.weight_kg, 70),
    activity_level: form.activity_level,
    measurements: {
      chest_cm: optionalFloat(form.chest_cm),
      waist_cm: optionalFloat(form.waist_cm),
      hips_cm: optionalFloat(form.hips_cm),
    },
    training_days: form.activity_level === 'sedentary' ? [] : form.training_days,
    sport_types: form.activity_level === 'sedentary' ? [] : splitList(form.sport_text),
    goal: form.goal,
    allergies: uniqList([...form.allergies, ...splitList(form.custom_allergies)]),
    disliked_foods: splitList(form.disliked_foods),
    diet_type: null,
    budget_rub_week: optionalInt(form.budget_rub_week),
    cooking_frequency: form.cooking_frequency,
    cooking_time_budget: {
      minutes: Math.max(0, Math.round(parseNumber(form.cook_minutes, 0))),
      period: form.cook_period,
    },
    family_size: Math.max(1, Math.round(parseNumber(form.family_size, 1))),
    kitchen_equipment: form.kitchen_equipment,
    eating_schedule: {
      meals,
      ...Object.fromEntries(meals.map((meal) => [meal.id, meal.time])),
    },
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

function SingleChips({ options, value, onChange }: { options: Array<{ id: string; label: string }>; value: string; onChange: (value: string) => void }) {
  return (
    <View style={s.chipRow}>
      {options.map((option) => {
        const active = option.id === value;
        return (
          <TouchableOpacity key={option.id} style={[s.chip, active && s.chipActive]} onPress={() => onChange(option.id)} activeOpacity={0.75}>
            <Text style={[s.chipText, active && s.chipTextActive]}>{option.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

function MultiChips({ options, value, onChange }: { options: string[]; value: string[]; onChange: (value: string[]) => void }) {
  const toggle = (item: string) => onChange(value.includes(item) ? value.filter((current) => current !== item) : [...value, item]);
  return (
    <View style={s.chipRow}>
      {options.map((option) => {
        const active = value.includes(option);
        return (
          <TouchableOpacity key={option} style={[s.chip, active && s.chipActive]} onPress={() => toggle(option)} activeOpacity={0.75}>
            <Text style={[s.chipText, active && s.chipTextActive]}>{option}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

function DayChips({ value, onChange }: { value: string[]; onChange: (value: string[]) => void }) {
  const toggle = (item: string) => onChange(value.includes(item) ? value.filter((current) => current !== item) : [...value, item]);
  return (
    <View style={s.chipRow}>
      {WEEK_DAYS.map((day) => {
        const active = value.includes(day.id);
        return (
          <TouchableOpacity key={day.id} style={[s.dayChip, active && s.chipActive]} onPress={() => toggle(day.id)} activeOpacity={0.75}>
            <Text style={[s.chipText, active && s.chipTextActive]}>{day.label}</Text>
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
  optional,
  keyboardType = 'numeric',
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  unit?: string;
  optional?: boolean;
  keyboardType?: 'default' | 'numeric';
}) {
  return (
    <View style={s.fieldRow}>
      <View style={{ flex: 1 }}>
        <Text style={s.fieldLabel}>{label}</Text>
        {optional && <Text style={s.optional}>необязательно</Text>}
      </View>
      <View style={s.inputWrap}>
        <TextInput style={s.input} value={value} onChangeText={onChangeText} keyboardType={keyboardType} placeholderTextColor={GRAY} />
        {!!unit && <Text style={s.unit}>{unit}</Text>}
      </View>
    </View>
  );
}

function TextArea({ value, onChangeText, placeholder }: { value: string; onChangeText: (value: string) => void; placeholder: string }) {
  return (
    <TextInput
      style={s.textArea}
      value={value}
      onChangeText={onChangeText}
      placeholder={placeholder}
      placeholderTextColor={GRAY}
      multiline
      textAlignVertical="top"
    />
  );
}

export default function ProfileSettingsScreen() {
  const clearPlan = usePlanStore((state) => state.clearPlan);
  const [form, setForm] = useState<ProfileForm>(defaultForm);
  const [loadedProfile, setLoadedProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    profileApi.get()
      .then((profile) => {
        if (!mounted) return;
        setLoadedProfile(profile);
        setForm(profileToForm(profile));
      })
      .catch((e: any) => {
        if (mounted) setError(e?.response?.data?.detail ?? 'Не удалось загрузить профиль');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const updateForm = (patch: Partial<ProfileForm>) => setForm((prev) => ({ ...prev, ...patch }));

  const goToProfile = () => {
    router.replace('/(tabs)/profile' as any);
  };

  const updateMeal = (id: string, patch: Partial<MealSlot>) => {
    updateForm({ meals: form.meals.map((meal) => meal.id === id ? { ...meal, ...patch } : meal) });
  };

  const addMeal = () => {
    const next = form.meals.length + 1;
    updateForm({ meals: [...form.meals, { id: `meal_${Date.now()}`, name: `Прием ${next}`, time: '12:00' }] });
  };

  const removeMeal = (id: string) => {
    if (form.meals.length <= 1) return;
    updateForm({ meals: form.meals.filter((meal) => meal.id !== id) });
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      const updated = await profileApi.update(buildPayload(form));
      if (shouldInvalidatePlan(loadedProfile, updated)) {
        await clearPlan();
      }
      setLoadedProfile(updated);
      goToProfile();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Не удалось сохранить профиль');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
          <View style={s.header}>
            <TouchableOpacity style={s.backBtn} onPress={goToProfile} activeOpacity={0.75}>
              <Text style={s.backText}>← Назад</Text>
            </TouchableOpacity>
            <Text style={s.title}>Настройки профиля</Text>
            <Text style={s.sub}>Здесь можно изменить все данные из вводной анкеты.</Text>
          </View>

          {loading ? (
            <View style={s.loadingBox}>
              <ActivityIndicator color={PRIMARY} />
              <Text style={s.loadingText}>Загружаем данные</Text>
            </View>
          ) : (
            <>
              <Text style={s.sectionTitle}>Имя</Text>
              <View style={s.card}>
                <Field label="Имя" value={form.name} onChangeText={(name) => updateForm({ name })} optional keyboardType="default" />
              </View>

              <Text style={s.sectionTitle}>Параметры</Text>
              <SingleChips options={SEX_OPTIONS} value={form.sex} onChange={(sex) => updateForm({ sex })} />
              <View style={s.card}>
                <Field label="Возраст" value={form.age} onChangeText={(age) => updateForm({ age })} unit="лет" />
                <Field label="Рост" value={form.height_cm} onChangeText={(height_cm) => updateForm({ height_cm })} unit="см" />
                <Field label="Вес" value={form.weight_kg} onChangeText={(weight_kg) => updateForm({ weight_kg })} unit="кг" />
                <Field label="Грудь" value={form.chest_cm} onChangeText={(chest_cm) => updateForm({ chest_cm })} unit="см" optional />
                <Field label="Талия" value={form.waist_cm} onChangeText={(waist_cm) => updateForm({ waist_cm })} unit="см" optional />
                <Field label="Бедра" value={form.hips_cm} onChangeText={(hips_cm) => updateForm({ hips_cm })} unit="см" optional />
              </View>

              <Text style={s.sectionTitle}>Активность</Text>
              <SingleChips options={ACTIVITY_OPTIONS} value={form.activity_level} onChange={(activity_level) => updateForm({ activity_level })} />
              {form.activity_level !== 'sedentary' && (
                <>
                  <Text style={s.sectionTitle}>Тренировки</Text>
                  <DayChips value={form.training_days} onChange={(training_days) => updateForm({ training_days })} />
                  <TextArea value={form.sport_text} onChangeText={(sport_text) => updateForm({ sport_text })} placeholder="Спорт через запятую: силовые, бег, йога" />
                </>
              )}

              <Text style={s.sectionTitle}>Цель</Text>
              <SingleChips options={GOALS} value={form.goal} onChange={(goal) => updateForm({ goal })} />

              <Text style={s.sectionTitle}>Расписание питания</Text>
              {form.meals.map((meal, index) => (
                <View key={meal.id} style={s.mealCard}>
                  <View style={s.mealHeader}>
                    <Text style={s.mealTitle}>Прием {index + 1}</Text>
                    {form.meals.length > 1 && (
                      <TouchableOpacity onPress={() => removeMeal(meal.id)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                        <Text style={s.removeText}>Удалить</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                  <TextInput
                    style={s.nameInput}
                    value={meal.name}
                    onChangeText={(name) => updateMeal(meal.id, { name })}
                    placeholder="Название приема"
                    placeholderTextColor={GRAY}
                  />
                  <TextInput
                    style={s.timeInput}
                    value={meal.time}
                    onChangeText={(time) => updateMeal(meal.id, { time })}
                    placeholder="Например: 08:33 или 10:15"
                    placeholderTextColor={GRAY}
                  />
                </View>
              ))}
              <TouchableOpacity style={s.addBtn} onPress={addMeal} activeOpacity={0.8}>
                <Text style={s.addBtnText}>+ Добавить прием пищи</Text>
              </TouchableOpacity>

              <Text style={s.sectionTitle}>Аллергии</Text>
              <MultiChips options={ALLERGY_OPTIONS} value={form.allergies} onChange={(allergies) => updateForm({ allergies })} />
              <TextArea value={form.custom_allergies} onChangeText={(custom_allergies) => updateForm({ custom_allergies })} placeholder="Свои аллергии через запятую: креветки" />

              <Text style={s.sectionTitle}>Нелюбимые продукты</Text>
              <TextArea value={form.disliked_foods} onChangeText={(disliked_foods) => updateForm({ disliked_foods })} placeholder="Например: печень, сельдерей, творог" />

              <Text style={s.sectionTitle}>Бюджет и готовка</Text>
              <View style={s.card}>
                <Field label="Бюджет" value={form.budget_rub_week} onChangeText={(budget_rub_week) => updateForm({ budget_rub_week })} unit="₽/нед" optional />
                <Field label="Семья" value={form.family_size} onChangeText={(family_size) => updateForm({ family_size })} unit="чел." />
              </View>

              <Text style={s.sectionTitle}>Время на готовку</Text>
              <View style={s.card}>
                <Field label="Сколько минут" value={form.cook_minutes} onChangeText={(cook_minutes) => updateForm({ cook_minutes })} unit="мин" />
              </View>
              <SingleChips
                options={[
                  { id: 'day', label: 'Минут в день' },
                  { id: 'week', label: 'Минут в неделю' },
                ]}
                value={form.cook_period}
                onChange={(cook_period) => updateForm({ cook_period: cook_period as 'day' | 'week' })}
              />
              <SingleChips options={COOKING_OPTIONS} value={form.cooking_frequency} onChange={(cooking_frequency) => updateForm({ cooking_frequency })} />

              <Text style={s.sectionTitle}>Кухонная техника</Text>
              <MultiChips options={EQUIPMENT_OPTIONS} value={form.kitchen_equipment} onChange={(kitchen_equipment) => updateForm({ kitchen_equipment })} />

              <Text style={s.sectionTitle}>Плановые отклонения</Text>
              <TextArea value={form.planned_deviations_text} onChangeText={(planned_deviations_text) => updateForm({ planned_deviations_text })} placeholder="Каждое отклонение с новой строки" />
              <View style={s.card}>
                <Field label="Гибкость" value={form.flexibility_pct} onChangeText={(flexibility_pct) => updateForm({ flexibility_pct })} unit="%" />
              </View>

              {!!error && <Text style={s.errorText}>{error}</Text>}

              <TouchableOpacity style={s.saveBtn} onPress={save} disabled={saving} activeOpacity={0.8}>
                {saving ? <ActivityIndicator color="#FFF" /> : <Text style={s.saveText}>Сохранить изменения</Text>}
              </TouchableOpacity>
              <TouchableOpacity style={s.secondaryBtn} onPress={() => loadedProfile && setForm(profileToForm(loadedProfile))} activeOpacity={0.75}>
                <Text style={s.secondaryText}>Вернуть как было</Text>
              </TouchableOpacity>
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16, paddingBottom: 36 },
  header: { gap: 6, marginBottom: 14 },
  backBtn: { alignSelf: 'flex-start', paddingVertical: 8, paddingRight: 12 },
  backText: { color: PRIMARY, fontSize: 15, fontWeight: '800' },
  title: { fontSize: 24, fontWeight: '800', color: BLACK },
  sub: { color: GRAY, fontSize: 13, lineHeight: 18 },
  loadingBox: { backgroundColor: CARD, borderRadius: 8, padding: 20, alignItems: 'center', gap: 8 },
  loadingText: { color: GRAY, fontSize: 14 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: BLACK, marginTop: 12, marginBottom: 8 },
  card: { backgroundColor: CARD, borderRadius: 8, paddingHorizontal: 12, marginBottom: 12, borderWidth: 1, borderColor: BORDER },
  fieldRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#F0EEE7' },
  fieldLabel: { fontSize: 15, color: BLACK },
  optional: { fontSize: 11, color: GRAY, marginTop: 2 },
  inputWrap: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  input: { minWidth: 84, color: PRIMARY, fontSize: 16, fontWeight: '800', textAlign: 'right' },
  unit: { color: GRAY, fontSize: 13 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  chip: { backgroundColor: CARD, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1.5, borderColor: BORDER },
  dayChip: { minWidth: 44, alignItems: 'center', backgroundColor: CARD, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 9, borderWidth: 1.5, borderColor: BORDER },
  chipActive: { backgroundColor: '#F0FDF4', borderColor: PRIMARY },
  chipText: { color: GRAY, fontSize: 13, fontWeight: '700' },
  chipTextActive: { color: PRIMARY },
  textArea: { minHeight: 48, backgroundColor: CARD, borderRadius: 8, borderWidth: 1, borderColor: BORDER, padding: 12, color: BLACK, fontSize: 15, marginBottom: 12 },
  mealCard: { backgroundColor: CARD, borderRadius: 8, padding: 14, borderWidth: 1, borderColor: BORDER, marginBottom: 12 },
  mealHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  mealTitle: { fontSize: 15, fontWeight: '800', color: BLACK },
  removeText: { color: DANGER, fontWeight: '700', fontSize: 13 },
  nameInput: { borderWidth: 1, borderColor: BORDER, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, color: BLACK, fontSize: 15, marginBottom: 8 },
  timeInput: { borderWidth: 1, borderColor: BORDER, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, color: PRIMARY, fontSize: 16, fontWeight: '800' },
  addBtn: { backgroundColor: CARD, borderRadius: 8, borderWidth: 1.5, borderColor: PRIMARY, paddingVertical: 14, alignItems: 'center', marginBottom: 12 },
  addBtnText: { color: PRIMARY, fontSize: 15, fontWeight: '800' },
  saveBtn: { marginTop: 8, borderRadius: 8, backgroundColor: PRIMARY, paddingVertical: 15, alignItems: 'center' },
  saveText: { color: '#FFF', fontSize: 16, fontWeight: '800' },
  secondaryBtn: { backgroundColor: CARD, borderRadius: 8, paddingVertical: 14, alignItems: 'center', marginTop: 8, borderWidth: 1, borderColor: BORDER },
  secondaryText: { color: GRAY, fontSize: 14, fontWeight: '700' },
  errorText: { color: DANGER, fontSize: 13, textAlign: 'center', marginVertical: 10 },
});
