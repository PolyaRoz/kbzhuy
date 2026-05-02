import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { useAuthStore } from '../../src/store/authStore';
import { profileApi, ProfileCreateRequest } from '../../src/api/profile';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';

const EXAMPLES = [
  'Пиво с друзьями по пятницам',
  'Ресторан по субботам',
  'Сладкое после обеда на работе',
  'Пицца по воскресеньям',
  'Бургер после тренировки в среду',
];

function parseJson<T>(value: string | undefined, fallback: T): T {
  try {
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

function optionalInt(value: string | undefined) {
  const parsed = parseInt(value || '', 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function optionalFloat(value: string | undefined) {
  const parsed = parseFloat((value || '').replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : null;
}

export default function Step5() {
  const params = useLocalSearchParams<Record<string, string>>();
  const setOnboardingCompleted = useAuthStore((state) => state.setOnboardingCompleted);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const [items, setItems] = useState<string[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const showError = (title: string, msg: string) => {
    if (typeof window !== 'undefined') {
      setErrorMsg(msg);
    } else {
      Alert.alert(title, msg);
    }
  };

  const addItem = () => {
    const text = inputText.trim();
    if (!text || items.length >= 10) return;
    setItems((prev) => [...prev, text]);
    setInputText('');
  };

  const handleFinish = async () => {
    setErrorMsg('');

    if (!isAuthenticated) {
      showError('Сессия потеряна', 'Сначала войдите или зарегистрируйтесь заново.');
      router.replace('/onboarding' as any);
      return;
    }

    setLoading(true);
    try {
      const scheduleMeals = parseJson<Array<{ id: string; name: string; time: string }>>(params.schedule_meals, []);
      const schedule = {
        meals: scheduleMeals,
        ...Object.fromEntries(scheduleMeals.map((meal) => [meal.id, meal.time])),
      };

      const deviations = items.map((description) => ({
        type: 'user_input',
        description,
        day_of_week: null,
        kcal_extra: 0,
      }));

      const profilePayload: ProfileCreateRequest = {
        name: params.name || null,
        sex: params.sex || 'female',
        age: parseInt(params.age || '30', 10),
        height_cm: parseFloat(params.height || '170'),
        weight_kg: parseFloat(params.weight || '70'),
        activity_level: params.activity || 'moderate',
        measurements: {
          chest_cm: optionalFloat(params.chest),
          waist_cm: optionalFloat(params.waist),
          hips_cm: optionalFloat(params.hips),
        },
        training_days: parseJson<string[]>(params.training_days, []),
        sport_types: parseJson<string[]>(params.sport_types, []),
        goal: params.goal || 'maintain',
        allergies: parseJson<string[]>(params.allergies, []),
        disliked_foods: parseJson<string[]>(params.disliked_foods, []),
        budget_rub_week: optionalInt(params.budget),
        cooking_frequency: params.cooking_frequency || 'twice_a_week',
        cooking_time_budget: parseJson<Record<string, number | string | null>>(params.cooking_time_budget, {}),
        kitchen_equipment: parseJson<string[]>(params.kitchen_equipment, []),
        eating_schedule: schedule,
        planned_deviations: deviations,
        flexibility_pct: 10,
      };

      try {
        await profileApi.onboarding(profilePayload);
      } catch (e: any) {
        const detail = e?.response?.data?.detail;
        if (detail === 'Profile already exists, use PATCH') {
          await profileApi.update(profilePayload);
        } else {
          throw e;
        }
      }

      await setOnboardingCompleted(true);
      router.replace('/(tabs)');
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      showError('Ошибка', detail || 'Не удалось сохранить профиль');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.container} keyboardShouldPersistTaps="handled">
        <View style={s.progressBar}><View style={[s.progressFill, { width: '100%' }]} /></View>
        <Text style={s.step}>Шаг 5 из 5</Text>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Text style={s.backText}>← Назад</Text>
        </TouchableOpacity>
        <Text style={s.title}>Почти готово</Text>
        <Text style={s.sub}>Добавьте плановые отклонения и сохраните анкету.</Text>

        <Text style={s.sectionTitle}>Плановые отклонения</Text>
        <Text style={s.sectionHint}>
          Например: ресторан по субботам, пицца по воскресеньям, сладкое после обеда.
        </Text>

        <View style={s.inputRow}>
          <TextInput
            style={s.input}
            placeholder="Например: пицца по воскресеньям"
            placeholderTextColor="#9CA3AF"
            value={inputText}
            onChangeText={setInputText}
            onSubmitEditing={addItem}
            returnKeyType="done"
            maxLength={100}
          />
          <TouchableOpacity style={[s.addBtn, !inputText.trim() && s.addBtnDisabled]} onPress={addItem} disabled={!inputText.trim()}>
            <Text style={s.addBtnText}>+</Text>
          </TouchableOpacity>
        </View>

        {items.map((item, index) => (
          <View key={`${item}-${index}`} style={s.chip}>
            <Text style={s.chipText}>{item}</Text>
            <TouchableOpacity onPress={() => setItems((prev) => prev.filter((_, i) => i !== index))}>
              <Text style={s.chipRemove}>✕</Text>
            </TouchableOpacity>
          </View>
        ))}

        {items.length === 0 && (
          <View style={s.examplesWrap}>
            {EXAMPLES.map((example) => (
              <TouchableOpacity
                key={example}
                style={s.exampleChip}
                onPress={() => setItems((prev) => (prev.includes(example) ? prev : [...prev, example]))}
              >
                <Text style={s.exampleText}>{example}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        <View style={s.summary}>
          <Text style={s.summaryTitle}>Профиль:</Text>
          <Text style={s.summaryRow}>Имя: <Text style={s.summaryVal}>{params.name || 'не указано'}</Text></Text>
          <Text style={s.summaryRow}>Цель: <Text style={s.summaryVal}>{params.goal || 'maintain'}</Text></Text>
          <Text style={s.summaryRow}>Вес: <Text style={s.summaryVal}>{params.weight || '—'} кг</Text></Text>
          <Text style={s.summaryRow}>Приемов пищи: <Text style={s.summaryVal}>{parseJson<any[]>(params.schedule_meals, []).length || 0}</Text></Text>
        </View>

        {!!errorMsg && <Text style={s.errorText}>{errorMsg}</Text>}

        <TouchableOpacity style={s.btn} onPress={handleFinish} activeOpacity={0.8} disabled={loading}>
          {loading ? <ActivityIndicator color="#FFF" /> : <Text style={s.btnText}>Сохранить анкету</Text>}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  container: { padding: 24, paddingBottom: 36 },
  progressBar: { height: 4, backgroundColor: PRIMARY, borderRadius: 2, marginBottom: 6 },
  progressFill: { height: 4, backgroundColor: PRIMARY, borderRadius: 2 },
  step: { fontSize: 12, color: GRAY, marginBottom: 12 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  backBtn: { alignSelf: 'flex-start', paddingVertical: 8, paddingRight: 12, marginBottom: 8 },
  backText: { color: PRIMARY, fontSize: 15, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  title: { fontSize: 26, fontWeight: '800', color: BLACK, marginBottom: 6 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.52},
  sub: { fontSize: 14, color: GRAY, marginBottom: 20 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  sectionTitle: { fontSize: 15, fontWeight: '800', color: BLACK, marginBottom: 4 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3},
  sectionHint: { fontSize: 12, color: GRAY, marginBottom: 10 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  inputRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  input: { flex: 1, backgroundColor: '#FFF', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: BLACK, borderWidth: 1, borderColor: '#D4DAD5' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  addBtn: { width: 48, height: 48, borderRadius: 8, backgroundColor: PRIMARY, alignItems: 'center', justifyContent: 'center' },
  addBtnDisabled: { backgroundColor: '#D1D5DB' },
  addBtnText: { color: '#FFF', fontSize: 24, fontWeight: '800', marginTop: -2 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  chip: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F0FDF4', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, marginBottom: 8, borderWidth: 1, borderColor: '#BBF7D0', gap: 10 },
  chipText: { flex: 1, fontSize: 14, color: BLACK , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  chipRemove: { fontSize: 14, color: GRAY, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  examplesWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 },
  exampleChip: { backgroundColor: '#FFF', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7, borderWidth: 1, borderColor: '#D4DAD5' },
  exampleText: { fontSize: 12, color: GRAY, fontWeight: '600' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  summary: { backgroundColor: '#F0FDF4', borderRadius: 8, padding: 16, marginTop: 20, marginBottom: 20, borderWidth: 1, borderColor: '#BBF7D0' },
  summaryTitle: { fontSize: 15, fontWeight: '800', color: BLACK, marginBottom: 10 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3},
  summaryRow: { fontSize: 14, color: GRAY, marginBottom: 4 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  summaryVal: { fontWeight: '800', color: BLACK },
  errorText: { color: '#C8553D', fontSize: 13, textAlign: 'center', marginBottom: 12 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  btn: { backgroundColor: PRIMARY, borderRadius: 8, paddingVertical: 16, alignItems: 'center' },
  btnText: { color: '#FFF', fontSize: 16, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
});
