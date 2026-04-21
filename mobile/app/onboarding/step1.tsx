import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useState } from 'react';

const PRIMARY = '#1A7340';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';
const BORDER = '#E5E7EB';

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

function Field({ label, value, onChangeText, unit, optional, keyboardType = 'numeric' }: any) {
  return (
    <View style={s.fieldRow}>
      <View style={{ flex: 1 }}>
        <Text style={s.fieldLabel}>{label}</Text>
        {optional && <Text style={s.optional}>необязательно</Text>}
      </View>
      <View style={s.inputWrap}>
        <TextInput
          style={s.input}
          value={value}
          onChangeText={onChangeText}
          keyboardType={keyboardType}
          placeholderTextColor={GRAY}
        />
        {!!unit && <Text style={s.unit}>{unit}</Text>}
      </View>
    </View>
  );
}

export default function Step1() {
  const [name, setName] = useState('');
  const [sex, setSex] = useState<'male' | 'female'>('female');
  const [age, setAge] = useState('30');
  const [height, setHeight] = useState('170');
  const [weight, setWeight] = useState('70');
  const [activity, setActivity] = useState('moderate');
  const [chest, setChest] = useState('');
  const [waist, setWaist] = useState('');
  const [hips, setHips] = useState('');
  const [trainingDays, setTrainingDays] = useState<string[]>([]);
  const [sportText, setSportText] = useState('');

  const toggleDay = (day: string) => {
    setTrainingDays((prev) => prev.includes(day) ? prev.filter((item) => item !== day) : [...prev, day]);
  };

  const handleNext = () => {
    if (!age.trim() || !height.trim() || !weight.trim()) return;
    router.push({
      pathname: '/onboarding/step2',
      params: {
        name: name.trim(),
        sex,
        age,
        height,
        weight,
        activity,
        chest,
        waist,
        hips,
        training_days: JSON.stringify(trainingDays),
        sport_types: JSON.stringify(sportText.split(',').map((item) => item.trim()).filter(Boolean)),
      },
    });
  };

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={s.container} keyboardShouldPersistTaps="handled">
          <View style={s.progressBar}><View style={[s.progressFill, { width: '20%' }]} /></View>
          <Text style={s.step}>Шаг 1 из 5</Text>
          <Text style={s.title}>Давайте настроим профиль</Text>
          <Text style={s.sub}>Имя, параметры и активность нужны для расчета КБЖУ</Text>

          <View style={s.card}>
            <Field label="Имя" value={name} onChangeText={setName} optional keyboardType="default" />
            <Field label="Возраст" value={age} onChangeText={setAge} unit="лет" />
            <Field label="Рост" value={height} onChangeText={setHeight} unit="см" />
            <Field label="Вес" value={weight} onChangeText={setWeight} unit="кг" />
          </View>

          <Text style={s.sectionTitle}>Пол</Text>
          <View style={s.twoCol}>
            {(['female', 'male'] as const).map((value) => (
              <TouchableOpacity key={value} style={[s.choice, sex === value && s.choiceActive]} onPress={() => setSex(value)}>
                <Text style={[s.choiceText, sex === value && s.choiceTextActive]}>{value === 'female' ? 'Женщина' : 'Мужчина'}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={s.sectionTitle}>Активность</Text>
          {ACTIVITY_OPTIONS.map((option) => (
            <TouchableOpacity key={option.id} style={[s.activityBtn, activity === option.id && s.choiceActive]} onPress={() => setActivity(option.id)}>
              <Text style={[s.choiceText, activity === option.id && s.choiceTextActive]}>{option.label}</Text>
            </TouchableOpacity>
          ))}

          {activity !== 'sedentary' && (
            <>
              <Text style={s.sectionTitle}>Тренировки</Text>
              <Text style={s.sectionHint}>Необязательно, но поможет точнее распределять еду по дням</Text>
              <View style={s.dayRow}>
                {WEEK_DAYS.map((day) => {
                  const active = trainingDays.includes(day.id);
                  return (
                    <TouchableOpacity key={day.id} style={[s.dayChip, active && s.choiceActive]} onPress={() => toggleDay(day.id)}>
                      <Text style={[s.dayText, active && s.choiceTextActive]}>{day.label}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
              <TextInput
                style={s.textInput}
                value={sportText}
                onChangeText={setSportText}
                placeholder="Например: силовые, бег, йога"
                placeholderTextColor={GRAY}
              />
            </>
          )}

          <Text style={s.sectionTitle}>Замеры тела</Text>
          <Text style={s.sectionHint}>Необязательно. Можно оставить пустым.</Text>
          <View style={s.card}>
            <Field label="Грудь" value={chest} onChangeText={setChest} unit="см" optional />
            <Field label="Талия" value={waist} onChangeText={setWaist} unit="см" optional />
            <Field label="Бедра" value={hips} onChangeText={setHips} unit="см" optional />
          </View>

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
  progressBar: { height: 4, backgroundColor: '#E5E7EB', borderRadius: 2, marginBottom: 6 },
  progressFill: { height: 4, backgroundColor: PRIMARY, borderRadius: 2 },
  step: { fontSize: 12, color: GRAY, marginBottom: 24 },
  title: { fontSize: 26, fontWeight: '800', color: BLACK, marginBottom: 6 },
  sub: { fontSize: 14, color: GRAY, marginBottom: 22 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: BLACK, marginBottom: 8, marginTop: 8 },
  sectionHint: { fontSize: 12, color: GRAY, marginBottom: 10 },
  card: { backgroundColor: CARD, borderRadius: 8, paddingHorizontal: 14, marginBottom: 16, borderWidth: 1, borderColor: BORDER },
  fieldRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#F3F4F6' },
  fieldLabel: { fontSize: 15, color: BLACK },
  optional: { fontSize: 11, color: GRAY, marginTop: 2 },
  inputWrap: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  input: { fontSize: 17, fontWeight: '800', color: PRIMARY, textAlign: 'right', minWidth: 84 },
  unit: { fontSize: 13, color: GRAY },
  twoCol: { flexDirection: 'row', gap: 10, marginBottom: 14 },
  choice: { flex: 1, backgroundColor: CARD, borderRadius: 8, paddingVertical: 12, alignItems: 'center', borderWidth: 1.5, borderColor: BORDER },
  activityBtn: { backgroundColor: CARD, borderRadius: 8, padding: 14, marginBottom: 8, borderWidth: 1.5, borderColor: BORDER },
  choiceActive: { borderColor: PRIMARY, backgroundColor: '#F0FDF4' },
  choiceText: { color: GRAY, fontSize: 14, fontWeight: '700' },
  choiceTextActive: { color: PRIMARY },
  dayRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 10 },
  dayChip: { minWidth: 44, alignItems: 'center', borderRadius: 8, paddingVertical: 9, paddingHorizontal: 10, backgroundColor: CARD, borderWidth: 1.5, borderColor: BORDER },
  dayText: { color: GRAY, fontWeight: '800' },
  textInput: { backgroundColor: CARD, borderRadius: 8, borderWidth: 1, borderColor: BORDER, padding: 13, fontSize: 15, color: BLACK, marginBottom: 16 },
  btn: { backgroundColor: PRIMARY, borderRadius: 8, paddingVertical: 16, alignItems: 'center', marginTop: 10 },
  btnText: { color: '#FFF', fontSize: 17, fontWeight: '800' },
});
