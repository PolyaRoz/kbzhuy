import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

const PRIMARY = '#1A7340';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';
const BORDER = '#E5E7EB';

type MealSlot = { id: string; name: string; time: string };

const DEFAULT_MEALS: MealSlot[] = [
  { id: 'meal_1', name: 'Завтрак', time: '08:00' },
  { id: 'meal_2', name: 'Обед', time: '13:00' },
  { id: 'meal_3', name: 'Перекус', time: '16:00' },
  { id: 'meal_4', name: 'Ужин', time: '19:00' },
];

export default function Step3() {
  const params = useLocalSearchParams<Record<string, string>>();
  const [meals, setMeals] = useState<MealSlot[]>(DEFAULT_MEALS);

  const updateMeal = (id: string, patch: Partial<MealSlot>) => {
    setMeals((prev) => prev.map((meal) => meal.id === id ? { ...meal, ...patch } : meal));
  };

  const addMeal = () => {
    const next = meals.length + 1;
    setMeals((prev) => [...prev, { id: `meal_${Date.now()}`, name: `Прием ${next}`, time: '12:00' }]);
  };

  const removeMeal = (id: string) => {
    setMeals((prev) => prev.length > 1 ? prev.filter((meal) => meal.id !== id) : prev);
  };

  const handleNext = () => {
    const cleanMeals = meals
      .map((meal, index) => ({
        id: `meal_${index + 1}`,
        name: meal.name.trim() || `Прием ${index + 1}`,
        time: meal.time.trim() || '12:00',
      }))
      .sort((a, b) => a.time.localeCompare(b.time));

    router.push({
      pathname: '/onboarding/step4',
      params: {
        ...params,
        schedule_meals: JSON.stringify(cleanMeals),
        schedule: JSON.stringify(Object.fromEntries(cleanMeals.map((meal) => [meal.id, meal.time]))),
      },
    });
  };

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={s.container} keyboardShouldPersistTaps="handled">
          <View style={s.progressBar}><View style={[s.progressFill, { width: '60%' }]} /></View>
          <Text style={s.step}>Шаг 3 из 5</Text>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
            <Text style={s.backText}>← Назад</Text>
          </TouchableOpacity>
          <Text style={s.title}>Расписание питания</Text>
          <Text style={s.sub}>Можно оставить один прием пищи или добавить хоть семь. Введите удобное время вручную.</Text>

          {meals.map((meal, index) => (
            <View key={meal.id} style={s.mealCard}>
              <View style={s.mealHeader}>
                <Text style={s.mealTitle}>Прием {index + 1}</Text>
                {meals.length > 1 && (
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
                placeholder="Например: 11:00 или 01:00"
                placeholderTextColor={GRAY}
              />
            </View>
          ))}

          <TouchableOpacity style={s.addBtn} onPress={addMeal} activeOpacity={0.8}>
            <Text style={s.addBtnText}>+ Добавить прием пищи</Text>
          </TouchableOpacity>

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
  step: { fontSize: 12, color: GRAY, marginBottom: 12 },
  backBtn: { alignSelf: 'flex-start', paddingVertical: 8, paddingRight: 12, marginBottom: 8 },
  backText: { color: PRIMARY, fontSize: 15, fontWeight: '800' },
  title: { fontSize: 26, fontWeight: '800', color: BLACK, marginBottom: 6 },
  sub: { fontSize: 14, color: GRAY, marginBottom: 20, lineHeight: 20 },
  mealCard: { backgroundColor: CARD, borderRadius: 8, padding: 14, borderWidth: 1, borderColor: BORDER, marginBottom: 12 },
  mealHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  mealTitle: { fontSize: 15, fontWeight: '800', color: BLACK },
  removeText: { color: '#DC2626', fontWeight: '700', fontSize: 13 },
  nameInput: { borderWidth: 1, borderColor: BORDER, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, color: BLACK, fontSize: 15, marginBottom: 8 },
  timeInput: { borderWidth: 1, borderColor: BORDER, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, color: PRIMARY, fontSize: 16, fontWeight: '800' },
  addBtn: { backgroundColor: CARD, borderRadius: 8, borderWidth: 1.5, borderColor: PRIMARY, paddingVertical: 14, alignItems: 'center', marginBottom: 12 },
  addBtnText: { color: PRIMARY, fontSize: 15, fontWeight: '800' },
  btn: { backgroundColor: PRIMARY, borderRadius: 8, paddingVertical: 16, alignItems: 'center' },
  btnText: { color: '#FFF', fontSize: 17, fontWeight: '800' },
});
