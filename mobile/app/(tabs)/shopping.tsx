import { useEffect, useMemo } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useShoppingStore, ShoppingItem } from '@/store/shoppingStore';

const PRIMARY = '#1A7340';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';

// ─── Category icons ──────────────────────────────────────────────────────────

const CATEGORY_ICON: Record<string, string> = {
  'мясо': '🥩', 'мясо и птица': '🥩', 'птица': '🍗',
  'крупы': '🌾', 'бакалея': '🌾',
  'молочка': '🥛', 'молочные': '🥛',
  'овощи': '🥦', 'овощи и зелень': '🥦', 'зелень': '🌿',
  'фрукты': '🍎',
  'специи': '🫙', 'специи и масла': '🫙', 'масла': '🫙',
  'рыба': '🐟', 'морепродукты': '🐟',
  'хлеб': '🍞', 'выпечка': '🍞',
  'напитки': '🥤',
};

function categoryIcon(cat: string): string {
  const lower = cat.toLowerCase();
  return CATEGORY_ICON[lower] ?? '🛒';
}

// ─── Group items by category ─────────────────────────────────────────────────

interface Group {
  category: string;
  icon: string;
  items: ShoppingItem[];
}

function groupByCategory(items: ShoppingItem[]): Group[] {
  const map = new Map<string, ShoppingItem[]>();
  for (const item of items) {
    const cat = item.category || 'Прочее';
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat)!.push(item);
  }
  return Array.from(map.entries()).map(([category, items]) => ({
    category,
    icon: categoryIcon(category),
    items,
  }));
}

// ─── Screen ──────────────────────────────────────────────────────────────────

export default function ShoppingScreen() {
  const { items, loading, error, fetchList, toggleItem } = useShoppingStore();

  useEffect(() => {
    fetchList();
  }, []);

  const groups = useMemo(() => groupByCategory(items), [items]);

  const totalItems = items.length;
  const checkedItems = items.filter((it) => it.checked).length;
  const toBuyItems = items.filter((it) => !it.at_home && !it.checked).length;
  const progress = totalItems > 0 ? checkedItems / totalItems : 0;

  if (loading && items.length === 0) {
    return (
      <SafeAreaView style={s.safe}>
        <Text style={s.title}>Покупки</Text>
        <ActivityIndicator color={PRIMARY} style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }

  if (error && items.length === 0) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.content}>
          <Text style={s.title}>Покупки</Text>
          <View style={s.emptyCard}>
            <Text style={s.emptyText}>Нет списка покупок</Text>
            <Text style={s.emptyHint}>Сначала создайте план питания на вкладке «План»</Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  if (totalItems === 0) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.content}>
          <Text style={s.title}>Покупки</Text>
          <View style={s.emptyCard}>
            <Text style={s.emptyText}>Список пуст</Text>
            <Text style={s.emptyHint}>Создайте план питания — список покупок сформируется автоматически</Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>

        <Text style={s.title}>Покупки</Text>

        {/* Progress card */}
        <View style={s.progressCard}>
          <View style={s.progressRow}>
            <View>
              <Text style={s.progressLabel}>Список на эту неделю</Text>
              <Text style={s.progressCount}>{checkedItems} из {totalItems} позиций</Text>
            </View>
            <View style={s.progressCircle}>
              <Text style={s.progressPct}>{Math.round(progress * 100)}%</Text>
            </View>
          </View>
          <View style={s.progressBar}>
            <View style={[s.progressFill, { width: `${progress * 100}%` as any }]} />
          </View>
          {toBuyItems > 0 && (
            <Text style={s.progressSub}>Нужно купить: {toBuyItems} позиций</Text>
          )}
        </View>

        {/* Legend */}
        <View style={s.legendRow}>
          <View style={s.legendItem}><View style={[s.legendDot, { backgroundColor: '#D1FAE5' }]} /><Text style={s.legendText}>есть дома</Text></View>
          <View style={s.legendItem}><View style={[s.legendDot, { backgroundColor: '#FFF' }]} /><Text style={s.legendText}>нужно купить</Text></View>
        </View>

        {/* Groups */}
        {groups.map((group) => (
          <View key={group.category} style={s.group}>
            <View style={s.groupHeader}>
              <Text style={s.groupIcon}>{group.icon}</Text>
              <Text style={s.groupName}>{group.category}</Text>
              <Text style={s.groupCount}>{group.items.filter((it) => !it.checked && !it.at_home).length} осталось</Text>
            </View>
            {group.items.map((item) => (
              <TouchableOpacity
                key={item.id}
                style={[s.item, item.at_home && s.itemAtHome, item.checked && s.itemChecked]}
                onPress={() => toggleItem(item.id)}
                activeOpacity={0.6}
              >
                <View style={[s.checkbox, item.checked && s.checkboxChecked]}>
                  {item.checked && <Text style={s.checkmark}>✓</Text>}
                </View>
                <View style={s.itemBody}>
                  <Text style={[s.itemName, item.checked && s.itemNameChecked]}>{item.name}</Text>
                  {item.at_home && <View style={s.atHomeBadge}><Text style={s.atHomeBadgeText}>есть дома</Text></View>}
                </View>
                <Text style={[s.itemQty, item.checked && s.itemQtyChecked]}>{item.quantity}</Text>
              </TouchableOpacity>
            ))}
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

  emptyCard: { backgroundColor: CARD, borderRadius: 16, padding: 24, alignItems: 'center' },
  emptyText: { fontSize: 16, fontWeight: '600', color: BLACK, marginBottom: 6 },
  emptyHint: { fontSize: 13, color: GRAY, textAlign: 'center' },

  progressCard: { backgroundColor: CARD, borderRadius: 16, padding: 16, marginBottom: 10, boxShadow: '0 1px 6px rgba(0,0,0,0.04)' },
  progressRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  progressLabel: { fontSize: 13, color: GRAY, marginBottom: 2 },
  progressCount: { fontSize: 16, fontWeight: '700', color: BLACK },
  progressCircle: { width: 48, height: 48, borderRadius: 24, backgroundColor: '#D1FAE5', alignItems: 'center', justifyContent: 'center' },
  progressPct: { fontSize: 14, fontWeight: '800', color: PRIMARY },
  progressBar: { height: 8, backgroundColor: '#F3F4F6', borderRadius: 4, overflow: 'hidden' },
  progressFill: { height: 8, backgroundColor: PRIMARY, borderRadius: 4 },
  progressSub: { fontSize: 12, color: GRAY, marginTop: 6 },

  legendRow: { flexDirection: 'row', gap: 16, marginBottom: 8 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  legendDot: { width: 12, height: 12, borderRadius: 3, borderWidth: 1, borderColor: '#E5E7EB' },
  legendText: { fontSize: 12, color: GRAY },

  group: { marginBottom: 6 },
  groupHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8 },
  groupIcon: { fontSize: 16 },
  groupName: { fontSize: 13, fontWeight: '700', color: PRIMARY, textTransform: 'uppercase', letterSpacing: 0.5, flex: 1 },
  groupCount: { fontSize: 11, color: GRAY },

  item: { flexDirection: 'row', alignItems: 'center', backgroundColor: CARD, borderRadius: 12, padding: 12, gap: 10, marginBottom: 4, borderWidth: 1, borderColor: '#E5E7EB' },
  itemAtHome: { backgroundColor: '#F0FDF4', borderColor: '#BBF7D0' },
  itemChecked: { opacity: 0.55 },
  checkbox: { width: 22, height: 22, borderRadius: 7, borderWidth: 2, borderColor: '#D1D5DB', alignItems: 'center', justifyContent: 'center' },
  checkboxChecked: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  checkmark: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  itemBody: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 },
  itemName: { fontSize: 14, fontWeight: '500', color: BLACK },
  itemNameChecked: { textDecorationLine: 'line-through', color: GRAY },
  atHomeBadge: { backgroundColor: '#D1FAE5', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  atHomeBadgeText: { fontSize: 10, color: PRIMARY, fontWeight: '600' },
  itemQty: { fontSize: 13, color: GRAY, fontWeight: '500' },
  itemQtyChecked: { color: '#D1D5DB' },
});
