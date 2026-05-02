import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';
const BORDER = '#D4DAD5';

export default function TrayScreen() {
  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
        <Text style={s.title}>Поднос</Text>
        <View style={s.emptyCard}>
          <Text style={s.emptyText}>Лента в разработке</Text>
          <Text style={s.emptyHint}>Здесь будут советы, новости о питании и персональные инсайты.</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16 },
  title: {
    fontSize: 22,
    fontWeight: '800',
    color: BLACK,
    marginBottom: 16,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
    letterSpacing: -0.44,
  },
  emptyCard: {
    backgroundColor: CARD,
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: BORDER,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '600',
    color: BLACK,
    marginBottom: 6,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  emptyHint: {
    fontSize: 13,
    color: GRAY,
    textAlign: 'center',
    lineHeight: 18,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
});
