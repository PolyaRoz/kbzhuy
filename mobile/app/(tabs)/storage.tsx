import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const PRIMARY = '#1A7340';
const BLUE = '#2563EB';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';

const FRIDGE = [
  { label: '1А', desc: 'Куриные ножки + гречка', shelf: 'Полка 1', expiry: '3 апр', daysLeft: 5, kcal: 520 },
  { label: '1Б', desc: 'Котлеты + рис', shelf: 'Полка 1', expiry: '3 апр', daysLeft: 5, kcal: 490 },
  { label: '2А', desc: 'Куриные ножки + гречка', shelf: 'Полка 2', expiry: '3 апр', daysLeft: 5, kcal: 520 },
  { label: '2Б', desc: 'Котлеты + рис', shelf: 'Полка 2', expiry: '3 апр', daysLeft: 5, kcal: 490 },
  { label: '2Г', desc: 'Куриные ножки + гречка', shelf: 'Полка 2', expiry: '1 апр', daysLeft: 3, kcal: 520 },
];

const FREEZER = [
  { label: '3А', desc: 'Куриные ножки запас', shelf: 'Верхняя ячейка', expiry: '15 апр', daysLeft: 17, kcal: 440 },
  { label: '3Б', desc: 'Котлеты запас', shelf: 'Нижняя ячейка', expiry: '15 апр', daysLeft: 17, kcal: 380 },
];

const PANTRY = [
  { name: 'Гречка', qty: '300 г', shelf: 'Шкаф', expiry: 'июнь 2025' },
  { name: 'Рис', qty: '250 г', shelf: 'Шкаф', expiry: 'май 2025' },
  { name: 'Масло оливковое', qty: '0.4 л', shelf: 'Шкаф', expiry: 'авг 2025' },
];

const EXPIRING = [
  { id: 1, name: 'Творог 5%', qty: '200 г', loc: 'Холодильник, полка 1', days: 1, label: 'Истекает завтра' },
  { id: 2, name: 'Молоко', qty: '0.5 л', loc: 'Холодильник, дверца', days: 2, label: 'Через 2 дня' },
];

function SectionHeader({ color, icon, title, count }: { color: string; icon: string; title: string; count: number }) {
  return (
    <View style={sh.row}>
      <View style={[sh.dot, { backgroundColor: color }]} />
      <Text style={[sh.title, { color }]}>{icon} {title}</Text>
      <View style={[sh.badge, { backgroundColor: color + '18' }]}>
        <Text style={[sh.badgeText, { color }]}>{count}</Text>
      </View>
    </View>
  );
}
const sh = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 16, marginBottom: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  title: { fontSize: 15, fontWeight: '700', flex: 1 },
  badge: { borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  badgeText: { fontSize: 12, fontWeight: '700' },
});

function ContainerCard({ label, desc, shelf, expiry, daysLeft, kcal, blue }: { label: string; desc: string; shelf: string; expiry: string; daysLeft: number; kcal: number; blue?: boolean }) {
  const urgent = daysLeft <= 3;
  return (
    <View style={[cc.card, blue && cc.cardBlue]}>
      <View style={[cc.badge, blue && cc.badgeBlue]}>
        <Text style={[cc.badgeText, blue && cc.badgeTextBlue]}>{label}</Text>
      </View>
      <View style={cc.body}>
        <Text style={cc.desc}>{desc}</Text>
        <Text style={cc.shelf}>{shelf}</Text>
      </View>
      <View style={cc.right}>
        <View style={[cc.expiryBadge, urgent && cc.expiryBadgeUrgent]}>
          <Text style={[cc.expiryText, urgent && cc.expiryTextUrgent]}>{expiry}</Text>
        </View>
        <Text style={[cc.kcal, blue && { color: BLUE }]}>{kcal} ккал</Text>
      </View>
    </View>
  );
}
const cc = StyleSheet.create({
  card: { flexDirection: 'row', backgroundColor: '#F0FDF4', borderRadius: 13, padding: 12, marginBottom: 6, gap: 10, alignItems: 'center', borderWidth: 1, borderColor: '#BBF7D0' },
  cardBlue: { backgroundColor: '#EFF6FF', borderColor: '#BFDBFE' },
  badge: { width: 40, height: 40, borderRadius: 11, backgroundColor: '#D1FAE5', alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: PRIMARY },
  badgeBlue: { backgroundColor: '#DBEAFE', borderColor: BLUE },
  badgeText: { fontSize: 14, fontWeight: '900', color: PRIMARY },
  badgeTextBlue: { color: BLUE },
  body: { flex: 1 },
  desc: { fontSize: 13, fontWeight: '700', color: BLACK },
  shelf: { fontSize: 11, color: GRAY, marginTop: 1 },
  right: { alignItems: 'flex-end', gap: 4 },
  expiryBadge: { backgroundColor: '#F3F4F6', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  expiryBadgeUrgent: { backgroundColor: '#FEE2E2' },
  expiryText: { fontSize: 10, color: GRAY, fontWeight: '500' },
  expiryTextUrgent: { color: '#EF4444', fontWeight: '700' },
  kcal: { fontSize: 11, color: PRIMARY, fontWeight: '600' },
});

export default function StorageScreen() {
  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>

        {/* Stats row */}
        <Text style={s.title}>Хранение</Text>
        <View style={s.statsRow}>
          <View style={s.stat}><Text style={s.statNum}>7</Text><Text style={s.statLabel}>контейнеров</Text></View>
          <View style={s.statDivider} />
          <View style={s.stat}><Text style={[s.statNum, { color: PRIMARY }]}>5</Text><Text style={s.statLabel}>в холодильнике</Text></View>
          <View style={s.statDivider} />
          <View style={s.stat}><Text style={[s.statNum, { color: BLUE }]}>2</Text><Text style={s.statLabel}>в морозилке</Text></View>
        </View>

        {/* Fridge */}
        <SectionHeader color={PRIMARY} icon="🟢" title="Холодильник" count={FRIDGE.length} />
        {FRIDGE.map((c) => <ContainerCard key={c.label} {...c} />)}

        {/* Freezer */}
        <SectionHeader color={BLUE} icon="🔵" title="Морозилка" count={FREEZER.length} />
        {FREEZER.map((c) => <ContainerCard key={c.label} {...c} blue />)}

        {/* Pantry */}
        <SectionHeader color="#92400E" icon="🟤" title="Кладовая / шкаф" count={PANTRY.length} />
        {PANTRY.map((item) => (
          <View key={item.name} style={s.pantryCard}>
            <View style={s.pantryLeft}>
              <Text style={s.pantryName}>{item.name}</Text>
              <Text style={s.pantryShelf}>{item.shelf}</Text>
            </View>
            <View style={s.pantryRight}>
              <Text style={s.pantryQty}>{item.qty}</Text>
              <Text style={s.pantryExpiry}>до {item.expiry}</Text>
            </View>
          </View>
        ))}

        {/* Expiring soon */}
        <View style={s.expiringSectionHeader}>
          <Text style={s.expiringSectionTitle}>⚠️ Скоро испортится</Text>
        </View>

        {EXPIRING.map((item) => (
          <View key={item.id} style={s.expiryCard}>
            <View style={s.expiryTop}>
              <View>
                <Text style={s.expiryName}>{item.name}</Text>
                <Text style={s.expiryLoc}>{item.loc} · {item.qty}</Text>
              </View>
              <View style={[s.expiryDayBadge, item.days === 1 && s.expiryDayBadgeRed]}>
                <Text style={[s.expiryDayText, item.days === 1 && s.expiryDayTextRed]}>{item.label}</Text>
              </View>
            </View>
            <View style={s.expiryActions}>
              <TouchableOpacity style={s.expiryBtn} activeOpacity={0.7}>
                <Text style={s.expiryBtnText}>📋 Рецепт</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.expiryBtn, s.expiryBtnBlue]} activeOpacity={0.7}>
                <Text style={[s.expiryBtnText, { color: BLUE }]}>❄️ Заморозить</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.expiryBtn, s.expiryBtnRed]} activeOpacity={0.7}>
                <Text style={[s.expiryBtnText, { color: '#EF4444' }]}>🗑 Выбросить</Text>
              </TouchableOpacity>
            </View>
          </View>
        ))}

        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16 },
  title: { fontSize: 22, fontWeight: '800', color: BLACK, letterSpacing: -0.3, marginBottom: 12 },

  statsRow: { flexDirection: 'row', backgroundColor: '#FFFFFF', borderRadius: 16, padding: 16, marginBottom: 4, boxShadow: '0 1px 6px rgba(0,0,0,0.04)' },
  stat: { flex: 1, alignItems: 'center' },
  statNum: { fontSize: 20, fontWeight: '800', color: BLACK },
  statLabel: { fontSize: 10, color: GRAY, marginTop: 1, textAlign: 'center' },
  statDivider: { width: 1, backgroundColor: '#E5E7EB' },

  pantryCard: { flexDirection: 'row', justifyContent: 'space-between', backgroundColor: '#FFF7ED', borderRadius: 12, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: '#FED7AA' },
  pantryLeft: {},
  pantryName: { fontSize: 14, fontWeight: '700', color: BLACK },
  pantryShelf: { fontSize: 12, color: GRAY, marginTop: 1 },
  pantryRight: { alignItems: 'flex-end' },
  pantryQty: { fontSize: 14, fontWeight: '600', color: '#92400E' },
  pantryExpiry: { fontSize: 11, color: GRAY, marginTop: 1 },

  expiringSectionHeader: { flexDirection: 'row', alignItems: 'center', marginTop: 16, marginBottom: 8 },
  expiringSectionTitle: { fontSize: 15, fontWeight: '700', color: '#B45309' },

  expiryCard: { backgroundColor: '#FFF7ED', borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: '#FED7AA' },
  expiryTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 },
  expiryName: { fontSize: 15, fontWeight: '700', color: BLACK },
  expiryLoc: { fontSize: 12, color: GRAY, marginTop: 1 },
  expiryDayBadge: { backgroundColor: '#FEF3C7', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  expiryDayBadgeRed: { backgroundColor: '#FEE2E2' },
  expiryDayText: { fontSize: 11, fontWeight: '700', color: '#B45309' },
  expiryDayTextRed: { color: '#EF4444' },
  expiryActions: { flexDirection: 'row', gap: 8 },
  expiryBtn: { flex: 1, backgroundColor: '#FFF', borderRadius: 8, paddingVertical: 7, alignItems: 'center', borderWidth: 1, borderColor: '#FED7AA' },
  expiryBtnBlue: { borderColor: '#BFDBFE' },
  expiryBtnRed: { borderColor: '#FECACA' },
  expiryBtnText: { fontSize: 12, fontWeight: '600', color: PRIMARY },
});
