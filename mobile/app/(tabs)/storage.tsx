import { Ionicons } from '@expo/vector-icons';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StorageLocation, useStorageStore } from '@/store/storageStore';

const PRIMARY = '#2B3A2E';
const BLUE = '#4A5C4D';
const ORANGE = '#C9A14B';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';
const BORDER = '#D4DAD5';

const LOCATION_META: Record<string, { title: string; color: string; icon: string }> = {
  fridge: { title: 'Холодильник', color: PRIMARY, icon: 'snow-outline' },
  freezer: { title: 'Морозилка', color: BLUE, icon: 'thermometer-outline' },
  pantry: { title: 'Шкаф', color: ORANGE, icon: 'layers-outline' },
};

export default function StorageScreen() {
  const { locations, loading, error, fetchAll, addItem, useItem, deleteItem, clearLocation } = useStorageStore();
  const [name, setName] = useState('');
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit] = useState('г');
  const [locationType, setLocationType] = useState<'fridge' | 'freezer' | 'pantry'>('pantry');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [useQuantity, setUseQuantity] = useState('');
  const [clearing, setClearing] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState<string | null>(null);

  // All sections collapsed by default
  const [openLocations, setOpenLocations] = useState<Set<string>>(new Set());

  const toggleLocation = (type: string) => {
    setOpenLocations((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const totalItems = useMemo(
    () => locations.reduce((sum, location) => sum + location.items.length, 0),
    [locations],
  );

  const handleAdd = async () => {
    const parsedQuantity = Number(quantity.replace(',', '.'));
    if (!name.trim() || !parsedQuantity || parsedQuantity <= 0) return;
    await addItem({
      name: name.trim(),
      quantity: parsedQuantity,
      unit,
      location_type: locationType,
    });
    setName('');
    setQuantity('');
    setUnit('г');
  };

  const handleUse = async (itemId: number) => {
    const parsedQuantity = Number(useQuantity.replace(',', '.'));
    if (!parsedQuantity || parsedQuantity <= 0) return;
    await useItem(itemId, parsedQuantity);
    setExpandedId(null);
    setUseQuantity('');
  };

  const handleClearTap = (key: string) => {
    if (confirmClear === key) {
      setConfirmClear(null);
      const locType = key === 'all' ? undefined : (key as 'fridge' | 'freezer' | 'pantry');
      setClearing(key);
      clearLocation(locType).finally(() => setClearing(null));
    } else {
      setConfirmClear(key);
      setTimeout(() => setConfirmClear((prev) => (prev === key ? null : prev)), 3000);
    }
  };

  if (loading && locations.length === 0) {
    return (
      <SafeAreaView style={s.safe}>
        <Text style={s.title}>Хранение</Text>
        <ActivityIndicator color={PRIMARY} style={s.loader} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
        <Text style={s.title}>Хранение</Text>

        <View style={s.statsRow}>
          <View style={s.stat}>
            <Text style={s.statNum}>{totalItems}</Text>
            <Text style={s.statLabel}>позиций</Text>
          </View>
          <View style={s.stat}>
            <Text style={s.statNum}>{locations.find((item) => item.type === 'fridge')?.items.length ?? 0}</Text>
            <Text style={s.statLabel}>в холодильнике</Text>
          </View>
          <View style={s.stat}>
            <Text style={s.statNum}>{locations.find((item) => item.type === 'freezer')?.items.length ?? 0}</Text>
            <Text style={s.statLabel}>в морозилке</Text>
          </View>
          <View style={s.stat}>
            <Text style={s.statNum}>{locations.find((item) => item.type === 'pantry')?.items.length ?? 0}</Text>
            <Text style={s.statLabel}>в шкафу</Text>
          </View>
        </View>

        <View style={s.formCard}>
          <Text style={s.formTitle}>Добавить продукт</Text>
          <TextInput style={s.input} placeholder="Название продукта" placeholderTextColor={GRAY} value={name} onChangeText={setName} />
          <View style={s.row}>
            <TextInput style={[s.input, s.inputHalf]} placeholder="Количество" placeholderTextColor={GRAY} keyboardType="numeric" value={quantity} onChangeText={setQuantity} />
            <TextInput style={[s.input, s.inputHalf]} placeholder="Единица" placeholderTextColor={GRAY} value={unit} onChangeText={setUnit} />
          </View>
          <View style={s.segmentRow}>
            {(['fridge', 'freezer', 'pantry'] as const).map((value) => (
              <TouchableOpacity
                key={value}
                style={[s.segmentBtn, locationType === value && s.segmentBtnActive]}
                onPress={() => setLocationType(value)}
              >
                <Ionicons
                  name={LOCATION_META[value].icon as any}
                  size={12}
                  color={locationType === value ? '#FFF' : GRAY}
                />
                <Text style={[s.segmentText, locationType === value && s.segmentTextActive]}>
                  {LOCATION_META[value].title}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <TouchableOpacity style={s.addBtn} onPress={handleAdd}>
            <Text style={s.addBtnText}>Добавить</Text>
          </TouchableOpacity>
        </View>

        {error ? <Text style={s.errorText}>{error}</Text> : null}

        {totalItems > 0 && (
          <TouchableOpacity
            style={[s.clearAllBtn, confirmClear === 'all' && s.clearAllBtnConfirm]}
            onPress={() => handleClearTap('all')}
            activeOpacity={0.8}
            disabled={clearing !== null}
          >
            {clearing === 'all' ? (
              <ActivityIndicator size="small" color="#C8553D" />
            ) : (
              <Text style={s.clearAllBtnText}>
                {confirmClear === 'all' ? 'Нажмите ещё раз для подтверждения' : 'Очистить всё хранение'}
              </Text>
            )}
          </TouchableOpacity>
        )}

        {locations.map((location) => (
          <LocationSection
            key={location.id}
            location={location}
            isOpen={openLocations.has(location.type)}
            onToggle={() => toggleLocation(location.type)}
            expandedId={expandedId}
            setExpandedId={setExpandedId}
            useQuantity={useQuantity}
            setUseQuantity={setUseQuantity}
            onUse={handleUse}
            onDelete={deleteItem}
            onClearTap={handleClearTap}
            clearing={clearing}
            confirmClear={confirmClear}
          />
        ))}
        <View style={s.bottomSpace} />
      </ScrollView>
    </SafeAreaView>
  );
}

function LocationSection({
  location,
  isOpen,
  onToggle,
  expandedId,
  setExpandedId,
  useQuantity,
  setUseQuantity,
  onUse,
  onDelete,
  onClearTap,
  clearing,
  confirmClear,
}: {
  location: StorageLocation;
  isOpen: boolean;
  onToggle: () => void;
  expandedId: number | null;
  setExpandedId: (value: number | null) => void;
  useQuantity: string;
  setUseQuantity: (value: string) => void;
  onUse: (itemId: number) => Promise<void>;
  onDelete: (itemId: number) => Promise<void>;
  onClearTap: (key: string) => void;
  clearing: string | null;
  confirmClear: string | null;
}) {
  const meta = LOCATION_META[location.type];
  const isClearing = clearing === location.type;
  const isPending = confirmClear === location.type;

  return (
    <View style={s.section}>
      {/* ── Collapsible header ── */}
      <TouchableOpacity style={s.sectionHeader} onPress={onToggle} activeOpacity={0.75}>
        <View style={[s.sectionIconWrap, { backgroundColor: `${meta.color}15`, borderColor: `${meta.color}30` }]}>
          <Ionicons name={meta.icon as any} size={16} color={meta.color} />
        </View>
        <Text style={[s.sectionTitle, { color: meta.color }]}>{meta.title}</Text>
        <Text style={s.sectionCount}>{location.items.length}</Text>
        {isOpen && location.items.length > 0 && (
          <TouchableOpacity
            style={[s.clearLocBtn, isPending && s.clearLocBtnConfirm]}
            onPress={() => onClearTap(location.type)}
            activeOpacity={0.8}
            disabled={clearing !== null}
          >
            {isClearing ? (
              <ActivityIndicator size="small" color="#C8553D" />
            ) : (
              <Text style={s.clearLocBtnText}>{isPending ? 'Точно?' : 'Очистить'}</Text>
            )}
          </TouchableOpacity>
        )}
        <Ionicons
          name={isOpen ? 'chevron-up' : 'chevron-down'}
          size={16}
          color={GRAY}
        />
      </TouchableOpacity>

      {/* ── Items: shown only when open ── */}
      {isOpen && (
        location.items.length === 0 ? (
          <View style={s.emptyLocation}>
            <Text style={s.emptyLocationText}>Пусто</Text>
          </View>
        ) : (
          location.items.map((item) => {
            const isExpanded = expandedId === item.id;
            return (
              <View key={item.id} style={s.itemCard}>
                <View style={s.itemTop}>
                  <TouchableOpacity style={s.itemMain} onPress={() => setExpandedId(isExpanded ? null : item.id)} activeOpacity={0.8}>
                    <View style={s.itemTextBlock}>
                      <Text style={s.itemName}>{item.name}</Text>
                      <Text style={s.itemMeta}>{item.category}</Text>
                    </View>
                    <Text style={s.itemQty}>{item.quantity} {item.unit}</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={s.trashBtn}
                    onPress={() => onDelete(item.id)}
                    activeOpacity={0.8}
                  >
                    <Ionicons name="trash-outline" size={16} color="#C8553D" />
                  </TouchableOpacity>
                </View>

                {isExpanded ? (
                  <View style={s.itemActions}>
                    <View style={s.row}>
                      <TextInput
                        style={[s.input, s.inputHalf]}
                        placeholder="Сколько использовано"
                        placeholderTextColor={GRAY}
                        keyboardType="numeric"
                        value={useQuantity}
                        onChangeText={setUseQuantity}
                      />
                      <TouchableOpacity style={[s.actionBtn, s.useBtn]} onPress={() => onUse(item.id)}>
                        <Text style={s.actionBtnText}>Использовать</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ) : null}
              </View>
            );
          })
        )
      )}
    </View>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { padding: 16 },
  loader: { marginTop: 40 },
  title: { fontSize: 22, fontWeight: '800', color: BLACK, marginBottom: 12, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.44 },
  statsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  stat: { flexGrow: 1, minWidth: 120, backgroundColor: CARD, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: BORDER },
  statNum: { fontSize: 20, fontWeight: '800', color: BLACK, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  statLabel: { fontSize: 11, color: GRAY, marginTop: 2, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  formCard: { backgroundColor: CARD, borderRadius: 16, padding: 14, marginBottom: 14, borderWidth: 1, borderColor: BORDER },
  formTitle: { fontSize: 16, fontWeight: '700', color: BLACK, marginBottom: 10, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.32 },
  row: { flexDirection: 'row', gap: 8 },
  input: { backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: BLACK, marginBottom: 8, flex: 1, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  inputHalf: { flex: 1 },
  segmentRow: { flexDirection: 'row', gap: 8, marginBottom: 10, flexWrap: 'wrap' },
  segmentBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: BORDER, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: CARD },
  segmentBtnActive: { borderColor: PRIMARY, backgroundColor: PRIMARY },
  segmentText: { color: GRAY, fontWeight: '600', fontSize: 13, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  segmentTextActive: { color: '#FFF' },
  addBtn: { backgroundColor: PRIMARY, borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  addBtnText: { color: '#FFF', fontSize: 14, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  errorText: { color: '#C8553D', marginBottom: 10 },

  // ── Sections ──
  section: { marginBottom: 8 },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: CARD,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: BORDER,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 4,
  },
  sectionIconWrap: {
    width: 32,
    height: 32,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sectionTitle: { fontSize: 15, fontWeight: '700', flex: 1, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3 },
  sectionCount: { fontSize: 12, color: GRAY, fontWeight: '600', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },

  emptyLocation: { backgroundColor: CARD, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: BORDER, marginBottom: 4 },
  emptyLocationText: { color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  itemCard: { backgroundColor: CARD, borderRadius: 12, padding: 12, marginBottom: 4, borderWidth: 1, borderColor: BORDER },
  itemTop: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  itemMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 },
  itemTextBlock: { flex: 1 },
  itemName: { fontSize: 14, fontWeight: '700', color: BLACK, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  itemMeta: { fontSize: 12, color: GRAY, marginTop: 2, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  itemQty: { fontSize: 14, fontWeight: '700', color: PRIMARY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  trashBtn: { width: 34, height: 34, borderRadius: 10, backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA', alignItems: 'center', justifyContent: 'center' },
  itemActions: { marginTop: 10 },
  actionBtn: { borderRadius: 10, paddingVertical: 10, alignItems: 'center', borderWidth: 1 },
  useBtn: { flex: 1, backgroundColor: '#E8E4D9', borderColor: BORDER },
  actionBtnText: { fontSize: 13, fontWeight: '700', color: PRIMARY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  bottomSpace: { height: 24 },
  clearAllBtn: { borderWidth: 1, borderColor: '#FECACA', borderRadius: 10, paddingVertical: 10, alignItems: 'center', backgroundColor: '#FEF2F2', marginBottom: 12 },
  clearAllBtnConfirm: { borderColor: '#C8553D', backgroundColor: '#FEF2F2' },
  clearAllBtnText: { color: '#C8553D', fontSize: 13, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  clearLocBtn: { borderWidth: 1, borderColor: '#FECACA', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, backgroundColor: '#FEF2F2', minWidth: 32, alignItems: 'center' },
  clearLocBtnConfirm: { borderColor: '#C8553D', backgroundColor: '#FEF2F2' },
  clearLocBtnText: { color: '#C8553D', fontSize: 11, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
});
