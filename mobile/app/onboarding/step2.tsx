import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

const PRIMARY = '#1A7340';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';
const BORDER = '#E5E7EB';

const GOALS = [
  { id: 'loss', icon: '📉', title: 'Похудение', desc: 'Снизить вес и процент жира' },
  { id: 'maintain', icon: '⚖️', title: 'Поддержание', desc: 'Стабильно держать форму' },
  { id: 'gain', icon: '📈', title: 'Набор массы', desc: 'Нарастить мышцы и вес' },
  { id: 'recomp', icon: '🔄', title: 'Рекомпозиция', desc: 'Меньше жира, больше мышц' },
];

export default function Step2() {
  const params = useLocalSearchParams<Record<string, string>>();
  const [selected, setSelected] = useState(params.goal || 'loss');

  const handleNext = () => {
    router.push({ pathname: '/onboarding/step3', params: { ...params, goal: selected } });
  };

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.container}>
        <View style={s.progressBar}><View style={[s.progressFill, { width: '40%' }]} /></View>
        <Text style={s.step}>Шаг 2 из 5</Text>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Text style={s.backText}>← Назад</Text>
        </TouchableOpacity>
        <Text style={s.title}>Какая у вас цель?</Text>
        <Text style={s.sub}>От цели зависит калорийность, белок и логика меню</Text>

        <View style={s.grid}>
          {GOALS.map((goal) => (
            <TouchableOpacity
              key={goal.id}
              style={[s.card, selected === goal.id && s.cardSelected]}
              onPress={() => setSelected(goal.id)}
              activeOpacity={0.8}
            >
              <Text style={s.cardIcon}>{goal.icon}</Text>
              <Text style={[s.cardTitle, selected === goal.id && s.cardTitleSelected]}>{goal.title}</Text>
              <Text style={s.cardDesc}>{goal.desc}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity style={s.btn} onPress={handleNext} activeOpacity={0.8}>
          <Text style={s.btnText}>Далее →</Text>
        </TouchableOpacity>
      </ScrollView>
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
  sub: { fontSize: 14, color: GRAY, marginBottom: 24 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 28 },
  card: { width: '47%', backgroundColor: CARD, borderRadius: 8, padding: 16, borderWidth: 1.5, borderColor: BORDER },
  cardSelected: { borderColor: PRIMARY, backgroundColor: '#F0FDF4' },
  cardIcon: { fontSize: 28, marginBottom: 8 },
  cardTitle: { fontSize: 15, fontWeight: '800', color: BLACK, marginBottom: 3 },
  cardTitleSelected: { color: PRIMARY },
  cardDesc: { fontSize: 12, color: GRAY },
  btn: { backgroundColor: PRIMARY, borderRadius: 8, paddingVertical: 16, alignItems: 'center' },
  btnText: { color: '#FFF', fontSize: 17, fontWeight: '800' },
});
