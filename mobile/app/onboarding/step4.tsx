import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';
const BORDER = '#D4DAD5';

const ALLERGY_OPTIONS = ['Лактоза', 'Глютен', 'Орехи', 'Яйца', 'Морепродукты', 'Соя'];
const EQUIPMENT_OPTIONS = ['Плита', 'Духовка', 'Микроволновка', 'Мультиварка', 'Блендер', 'Гриль'];
const COOKING_OPTIONS = [
  { id: 'daily', label: 'Каждый день' },
  { id: 'twice_a_week', label: '2 раза в неделю' },
  { id: 'once_a_week', label: '1 раз в неделю' },
];

function MultiChips({ options, value, onChange }: { options: string[]; value: string[]; onChange: (value: string[]) => void }) {
  const toggle = (item: string) => onChange(value.includes(item) ? value.filter((v) => v !== item) : [...value, item]);
  return (
    <View style={s.chipRow}>
      {options.map((option) => {
        const active = value.includes(option);
        return (
          <TouchableOpacity key={option} style={[s.chip, active && s.chipActive]} onPress={() => toggle(option)}>
            <Text style={[s.chipText, active && s.chipTextActive]}>{option}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

export default function Step4() {
  const params = useLocalSearchParams<Record<string, string>>();
  const [allergies, setAllergies] = useState<string[]>([]);
  const [customAllergies, setCustomAllergies] = useState('');
  const [dislikedFoods, setDislikedFoods] = useState('');
  const [budget, setBudget] = useState('');
  const [cookMinutes, setCookMinutes] = useState('60');
  const [cookPeriod, setCookPeriod] = useState<'day' | 'week'>('week');
  const [cookingFrequency, setCookingFrequency] = useState('twice_a_week');
  const [equipment, setEquipment] = useState<string[]>([]);

  const handleNext = () => {
    const custom = customAllergies.split(',').map((item) => item.trim()).filter(Boolean);
    router.push({
      pathname: '/onboarding/step5' as any,
      params: {
        ...params,
        allergies: JSON.stringify([...allergies, ...custom]),
        disliked_foods: JSON.stringify(dislikedFoods.split(',').map((item) => item.trim()).filter(Boolean)),
        budget,
        cooking_frequency: cookingFrequency,
        cooking_time_budget: JSON.stringify({ minutes: parseInt(cookMinutes || '0', 10) || 0, period: cookPeriod }),
        kitchen_equipment: JSON.stringify(equipment),
      },
    });
  };

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={s.container} keyboardShouldPersistTaps="handled">
          <View style={s.progressBar}><View style={[s.progressFill, { width: '80%' }]} /></View>
          <Text style={s.step}>Шаг 4 из 5</Text>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
            <Text style={s.backText}>← Назад</Text>
          </TouchableOpacity>
          <Text style={s.title}>Ограничения и готовка</Text>
          <Text style={s.sub}>Эти данные помогут делать меню реалистичным, а не идеальным на бумаге.</Text>

          <Text style={s.sectionTitle}>Аллергии</Text>
          <MultiChips options={ALLERGY_OPTIONS} value={allergies} onChange={setAllergies} />
          <TextInput
            style={s.textInput}
            value={customAllergies}
            onChangeText={setCustomAllergies}
            placeholder="Свои аллергии через запятую, например: креветки"
            placeholderTextColor={GRAY}
          />

          <Text style={s.sectionTitle}>Нелюбимые продукты</Text>
          <TextInput
            style={s.textInput}
            value={dislikedFoods}
            onChangeText={setDislikedFoods}
            placeholder="Например: печень, сельдерей, творог"
            placeholderTextColor={GRAY}
          />

          <Text style={s.sectionTitle}>Бюджет на еду</Text>
          <View style={s.card}>
            <View style={s.fieldRow}>
              <Text style={s.fieldLabel}>В неделю</Text>
              <View style={s.inputWrap}>
                <TextInput style={s.input} value={budget} onChangeText={setBudget} keyboardType="numeric" placeholder="3000" placeholderTextColor={GRAY} />
                <Text style={s.unit}>₽</Text>
              </View>
            </View>
          </View>

          <Text style={s.sectionTitle}>Время на готовку</Text>
          <View style={s.card}>
            <View style={s.fieldRow}>
              <Text style={s.fieldLabel}>Готова тратить</Text>
              <View style={s.inputWrap}>
                <TextInput style={s.input} value={cookMinutes} onChangeText={setCookMinutes} keyboardType="numeric" placeholder="60" placeholderTextColor={GRAY} />
                <Text style={s.unit}>мин</Text>
              </View>
            </View>
          </View>
          <View style={s.twoCol}>
            {(['day', 'week'] as const).map((period) => (
              <TouchableOpacity key={period} style={[s.choice, cookPeriod === period && s.chipActive]} onPress={() => setCookPeriod(period)}>
                <Text style={[s.choiceText, cookPeriod === period && s.chipTextActive]}>{period === 'day' ? 'в день' : 'в неделю'}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={s.sectionTitle}>Как часто готовить</Text>
          <View style={s.chipRow}>
            {COOKING_OPTIONS.map((option) => {
              const active = cookingFrequency === option.id;
              return (
                <TouchableOpacity key={option.id} style={[s.chip, active && s.chipActive]} onPress={() => setCookingFrequency(option.id)}>
                  <Text style={[s.chipText, active && s.chipTextActive]}>{option.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <Text style={s.sectionTitle}>Кухонная техника</Text>
          <MultiChips options={EQUIPMENT_OPTIONS} value={equipment} onChange={setEquipment} />

          <TouchableOpacity style={s.btn} onPress={handleNext} activeOpacity={0.8}>
            <Text style={s.btnText}>Далее →</Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  container: { padding: 24, paddingBottom: 36 },
  progressBar: { height: 4, backgroundColor: '#D4DAD5', borderRadius: 2, marginBottom: 6 },
  progressFill: { height: 4, backgroundColor: PRIMARY, borderRadius: 2 },
  step: { fontSize: 12, color: GRAY, marginBottom: 12 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  backBtn: { alignSelf: 'flex-start', paddingVertical: 8, paddingRight: 12, marginBottom: 8 },
  backText: { color: PRIMARY, fontSize: 15, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  title: { fontSize: 26, fontWeight: '800', color: BLACK, marginBottom: 6 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.52},
  sub: { fontSize: 14, color: GRAY, marginBottom: 20, lineHeight: 20 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  sectionTitle: { fontSize: 15, fontWeight: '800', color: BLACK, marginBottom: 8, marginTop: 8 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3},
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  chip: { borderRadius: 8, borderWidth: 1.5, borderColor: BORDER, backgroundColor: CARD, paddingHorizontal: 12, paddingVertical: 8 },
  chipActive: { borderColor: PRIMARY, backgroundColor: '#F0FDF4' },
  chipText: { color: GRAY, fontSize: 13, fontWeight: '700' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  chipTextActive: { color: PRIMARY },
  textInput: { backgroundColor: CARD, borderRadius: 8, borderWidth: 1, borderColor: BORDER, padding: 13, color: BLACK, fontSize: 15, marginBottom: 12 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  card: { backgroundColor: CARD, borderRadius: 8, paddingHorizontal: 14, marginBottom: 10, borderWidth: 1, borderColor: BORDER },
  fieldRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 12 },
  fieldLabel: { color: BLACK, fontSize: 15 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  inputWrap: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  input: { minWidth: 92, textAlign: 'right', fontSize: 17, color: PRIMARY, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  unit: { color: GRAY, fontSize: 13 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  twoCol: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  choice: { flex: 1, backgroundColor: CARD, borderWidth: 1.5, borderColor: BORDER, borderRadius: 8, paddingVertical: 12, alignItems: 'center' },
  choiceText: { color: GRAY, fontWeight: '800' },
  btn: { backgroundColor: PRIMARY, borderRadius: 8, paddingVertical: 16, alignItems: 'center', marginTop: 10 },
  btnText: { color: '#FFF', fontSize: 17, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
});
