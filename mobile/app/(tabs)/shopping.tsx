import { Ionicons } from '@expo/vector-icons';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { ShoppingItem, useShoppingStore } from '@/store/shoppingStore';
import { usePlanStore } from '@/store/planStore';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';

const MONTH_SHORT = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
function formatShortDate(iso?: string | null) {
  if (!iso) return '';
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getDate()} ${MONTH_SHORT[d.getMonth()]}`;
}

const CATEGORY_ICON: Record<string, string> = {
  'Мясо и птица': 'restaurant-outline',
  'Рыба и морепродукты': 'fish-outline',
  'Молочные продукты': 'cafe-outline',
  'Яйца': 'ellipse-outline',
  'Крупы и хлеб': 'nutrition-outline',
  'Овощи и зелень': 'leaf-outline',
  'Фрукты и ягоды': 'flower-outline',
  'Орехи и семечки': 'disc-outline',
  'Специи и масла': 'flask-outline',
  'Соусы и добавки': 'eyedrop-outline',
  'Напитки': 'water-outline',
  'Прочее': 'cube-outline',
};

function groupByCategory(items: ShoppingItem[]) {
  const map = new Map<string, ShoppingItem[]>();
  for (const item of items) {
    const category = item.category || 'Прочее';
    if (!map.has(category)) map.set(category, []);
    map.get(category)!.push(item);
  }
  return Array.from(map.entries()).map(([category, groupedItems]) => ({
    category,
    icon: CATEGORY_ICON[category] ?? 'cube-outline',
    items: groupedItems,
  }));
}

function formatItemQuantity(item: ShoppingItem) {
  const quantity = String(item.quantity ?? '').trim();
  const unit = String(item.unit ?? '').trim();
  if (!quantity) return unit;
  if (!unit) return quantity;
  if (quantity.toLowerCase().endsWith(unit.toLowerCase())) return quantity;
  return `${quantity} ${unit}`;
}

export default function ShoppingScreen() {
  const plan = usePlanStore((s) => s.plan);
  const planChecked = usePlanStore((s) => s.hasFetchedCurrent);
  const { items, loading, error, fetchList, confirmItems, markAllBought } = useShoppingStore();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // Re-fetch when plan appears (e.g. created from the Plan tab)
  useEffect(() => {
    if (plan) {
      void fetchList();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan]);

  useEffect(() => {
    setSelectedIds((current) =>
      current.filter((itemId) => items.some((item) => item.id === itemId && !item.checked && !item.at_home)),
    );
  }, [items]);

  // Items still needing to be bought (not yet at home)
  const toBuyList = useMemo(() => items.filter((item) => !item.at_home), [items]);
  const groups = useMemo(() => groupByCategory(toBuyList), [toBuyList]);
  const totalItems = items.length;
  const boughtItems = items.filter((item) => item.at_home).length;
  const toBuyItems = toBuyList.filter((item) => !item.checked).length;
  const selectedCount = selectedIds.length;
  const progress = totalItems > 0 ? boughtItems / totalItems : 0;

  const toggleSelected = (item: ShoppingItem) => {
    if (item.checked || item.at_home) return;
    setSelectedIds((current) =>
      current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id],
    );
  };

  const handleConfirm = async () => {
    if (!selectedIds.length) return;
    await confirmItems(selectedIds);
    setSelectedIds([]);
  };

  const clearSelected = () => {
    setSelectedIds([]);
  };

  if (planChecked && !plan) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.content}>
          <Text style={s.title}>Покупки</Text>
          <View style={s.noPlanCard}>
            <View style={s.noPlanIconWrap}>
              <Ionicons name="cart-outline" size={32} color={PRIMARY} />
            </View>
            <Text style={s.noPlanTitle}>Нет плана питания</Text>
            <Text style={s.noPlanHint}>Список покупок формируется автоматически из плана питания на неделю.</Text>
            <TouchableOpacity style={s.noPlanBtn} onPress={() => router.push('/(tabs)/plan')} activeOpacity={0.85}>
              <Text style={s.noPlanBtnText}>Создать план</Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  if (loading && items.length === 0) {
    return (
      <SafeAreaView style={s.safe}>
        <Text style={s.title}>Покупки</Text>
        <ActivityIndicator color={PRIMARY} style={s.centerLoader} />
      </SafeAreaView>
    );
  }

  if (error && items.length === 0) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.content}>
          <Text style={s.title}>Покупки</Text>
          <View style={s.emptyCard}>
            <Text style={s.emptyText}>Не удалось загрузить список</Text>
            <Text style={s.emptyHint}>Сначала собери план питания или обнови страницу.</Text>
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
            <Text style={s.emptyText}>Покупки закрыты</Text>
            <Text style={s.emptyHint}>Все нужные продукты уже есть дома или список ещё не сформирован.</Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  // All bought — show completion screen
  if (boughtItems === totalItems && totalItems > 0) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.content}>
          <Text style={s.title}>Покупки</Text>
          <View style={s.doneCard}>
            <View style={s.doneIconWrap}>
              <Ionicons name="checkmark" size={28} color="#5A7A5C" />
            </View>
            <Text style={s.doneTitle}>Список закрыт.</Text>
            <Text style={s.doneHint}>{totalItems} {totalItems === 1 ? 'позиция' : totalItems < 5 ? 'позиции' : 'позиций'} уже дома</Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
        <Text style={s.title}>Покупки</Text>

        <View style={s.toolbar}>
          <View style={s.confirmHint}>
            <Text style={s.confirmHintText}>
              {selectedCount > 0 ? `Выбрано: ${selectedCount}` : 'Отметь продукты, потом подтверди покупку внизу'}
            </Text>
          </View>

          <TouchableOpacity style={s.bulkBtn} onPress={markAllBought} activeOpacity={0.85}>
            <Text style={s.bulkBtnText}>Отметить всё куплено</Text>
          </TouchableOpacity>
        </View>

        <View style={s.progressCard}>
          <View style={s.progressRow}>
            <View>
              <Text style={s.progressLabel}>
                {plan
                  ? `Покупки: ${formatShortDate(plan.period_start)} — ${formatShortDate(plan.period_end)}`
                  : 'Покупки на следующий период'}
              </Text>
              <Text style={s.progressCount}>{boughtItems} из {totalItems} позиций</Text>
            </View>
            <View style={s.progressCircle}>
              <Text style={s.progressPct}>{Math.round(progress * 100)}%</Text>
            </View>
          </View>
          <View style={s.progressBar}>
            <View style={[s.progressFill, { width: `${progress * 100}%` }]} />
          </View>
          {toBuyItems > 0 ? <Text style={s.progressSub}>Осталось купить: {toBuyItems}</Text> : null}
        </View>

        {groups.map((group) => (
          <View key={group.category} style={s.group}>
            <View style={s.groupHeader}>
              <Ionicons name={group.icon as any} size={16} color={PRIMARY} />
              <Text style={s.groupName}>{group.category}</Text>
              <Text style={s.groupCount}>{group.items.filter((item) => !item.checked && !item.at_home).length} осталось</Text>
            </View>

            {group.items.map((item) => {
              const isSelected = selectedIds.includes(item.id);
              return (
                <TouchableOpacity
                  key={item.id}
                  style={[
                    s.item,
                    item.at_home && s.itemAtHome,
                    item.checked && s.itemChecked,
                    isSelected && s.itemSelected,
                  ]}
                  onPress={() => toggleSelected(item)}
                  activeOpacity={0.8}
                >
                  <View style={[s.checkbox, (item.checked || isSelected) && s.checkboxChecked]}>
                    {(item.checked || isSelected) ? <Ionicons name="checkmark" size={14} color="#FFF" /> : null}
                  </View>

                  <View style={s.itemBody}>
                    <Text style={[s.itemName, item.checked && s.itemNameChecked]}>{item.name}</Text>
                    {item.at_home ? (
                      <View style={s.atHomeBadge}>
                        <Text style={s.atHomeBadgeText}>уже дома</Text>
                      </View>
                    ) : null}
                  </View>

                  <Text style={[s.itemQty, item.checked && s.itemQtyChecked]}>
                    {formatItemQuantity(item)}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        ))}
        <View style={s.bottomSpace} />
      </ScrollView>

      {selectedCount > 0 ? (
        <View style={s.bottomBar}>
          <TouchableOpacity style={s.clearBtn} onPress={clearSelected} activeOpacity={0.85}>
            <Text style={s.clearBtnText}>Снять</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.bottomConfirmBtn} onPress={handleConfirm} activeOpacity={0.85}>
            <Text style={s.bottomConfirmText}>Купил: {selectedCount}</Text>
          </TouchableOpacity>
        </View>
      ) : null}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16 },
  centerLoader: { marginTop: 40 },
  title: { fontSize: 22, fontWeight: '800', color: BLACK, marginBottom: 12 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.44},
  toolbar: { flexDirection: 'row', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' },
  confirmBtn: { backgroundColor: PRIMARY, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10 },
  confirmBtnText: { color: '#FFF', fontSize: 13, fontWeight: '700' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  confirmHint: { backgroundColor: '#E8E4D9', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, flexShrink: 1 },
  confirmHintText: { color: PRIMARY, fontSize: 12, fontWeight: '600' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  bulkBtn: { backgroundColor: PRIMARY, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10 },
  bulkBtnText: { color: '#FFF', fontSize: 13, fontWeight: '700' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  bottomBar: {
    position: 'absolute',
    left: 16,
    right: 16,
    bottom: 16,
    flexDirection: 'row',
    gap: 8,
    backgroundColor: CARD,
    borderRadius: 14,
    padding: 10,
    borderWidth: 1,
    borderColor: '#D4DAD5',
    boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
  },
  clearBtn: {
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: '#F0EEE7',
    alignItems: 'center',
    justifyContent: 'center',
  },
  clearBtnText: { color: GRAY, fontSize: 13, fontWeight: '700' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  bottomConfirmBtn: {
    flex: 1,
    borderRadius: 10,
    paddingVertical: 12,
    backgroundColor: PRIMARY,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bottomConfirmText: { color: '#FFF', fontSize: 14, fontWeight: '800' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  emptyCard: { backgroundColor: CARD, borderRadius: 16, padding: 24, alignItems: 'center' },
  emptyText: { fontSize: 16, fontWeight: '600', color: BLACK, marginBottom: 6 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  emptyHint: { fontSize: 13, color: GRAY, textAlign: 'center' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  progressCard: { backgroundColor: CARD, borderRadius: 16, padding: 16, marginBottom: 10, boxShadow: '0 1px 6px rgba(0,0,0,0.04)' },
  progressRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  progressLabel: { fontSize: 13, color: GRAY, marginBottom: 2 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  progressCount: { fontSize: 16, fontWeight: '700', color: BLACK , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  progressCircle: { width: 48, height: 48, borderRadius: 24, backgroundColor: '#E8E4D9', alignItems: 'center', justifyContent: 'center' },
  progressPct: { fontSize: 14, fontWeight: '800', color: PRIMARY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  progressBar: { height: 8, backgroundColor: '#F0EEE7', borderRadius: 4, overflow: 'hidden' },
  progressFill: { height: 8, backgroundColor: PRIMARY, borderRadius: 4 },
  progressSub: { fontSize: 12, color: GRAY, marginTop: 6 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  group: { marginBottom: 6 },
  groupHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8 },
  groupName: { fontSize: 13, fontWeight: '700', color: PRIMARY, textTransform: 'uppercase', letterSpacing: 0.5, flex: 1 , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  groupCount: { fontSize: 11, color: GRAY , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  item: { flexDirection: 'row', alignItems: 'center', backgroundColor: CARD, borderRadius: 12, padding: 12, gap: 10, marginBottom: 4, borderWidth: 1, borderColor: '#D4DAD5' },
  itemAtHome: { backgroundColor: '#F0EEE7', borderColor: '#D4DAD5' },
  itemChecked: { opacity: 0.55 },
  itemSelected: { borderColor: PRIMARY, backgroundColor: '#F7FCF8' },
  checkbox: { width: 22, height: 22, borderRadius: 7, borderWidth: 2, borderColor: '#D4DAD5', alignItems: 'center', justifyContent: 'center' },
  checkboxChecked: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  itemBody: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  itemName: { fontSize: 14, fontWeight: '500', color: BLACK , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  itemNameChecked: { textDecorationLine: 'line-through', color: GRAY },
  atHomeBadge: { backgroundColor: '#E8E4D9', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  atHomeBadgeText: { fontSize: 10, color: PRIMARY, fontWeight: '600' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  itemQty: { fontSize: 13, color: GRAY, fontWeight: '500' , fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"},
  itemQtyChecked: { color: '#A8B5AA' },
  bottomSpace: { height: 104 },
  noPlanCard: { backgroundColor: CARD, borderRadius: 16, borderWidth: 1, borderColor: '#D4DAD5', padding: 24, alignItems: 'center', marginTop: 8 },
  noPlanIconWrap: { width: 64, height: 64, borderRadius: 32, backgroundColor: '#E8E4D9', alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  noPlanTitle: { fontSize: 18, fontWeight: '800', color: BLACK, marginBottom: 8, textAlign: 'center', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.36 },
  noPlanHint: { fontSize: 14, color: GRAY, lineHeight: 20, textAlign: 'center', marginBottom: 20, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  noPlanBtn: { backgroundColor: PRIMARY, borderRadius: 12, paddingHorizontal: 24, paddingVertical: 13 },
  noPlanBtnText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  doneCard: { backgroundColor: CARD, borderRadius: 16, borderWidth: 1, borderColor: '#D4DAD5', padding: 32, alignItems: 'center', marginTop: 8 },
  doneEmoji: { fontSize: 40, marginBottom: 12 },
  doneTitle: { fontSize: 20, fontWeight: '800', color: BLACK, marginBottom: 6, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.4 },
  doneHint: { fontSize: 14, color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
});
