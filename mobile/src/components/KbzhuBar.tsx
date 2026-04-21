import { StyleSheet, Text, View } from 'react-native';

interface Props {
  label: string;
  current: number;
  total: number;
  color: string;
}

export function KbzhuBar({ label, current, total, color }: Props) {
  const pct = total > 0 ? Math.min(current / total, 1) : 0;
  return (
    <View style={s.row}>
      <Text style={s.label}>{label}</Text>
      <View style={s.track}>
        <View style={[s.fill, { width: `${pct * 100}%` as any, backgroundColor: color }]} />
      </View>
      <Text style={s.value}>
        {current}<Text style={s.total}>/{total}</Text>
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 7 },
  label: { fontSize: 12, color: '#6B7280', fontWeight: '600', width: 28 },
  track: { flex: 1, height: 8, backgroundColor: '#F3F4F6', borderRadius: 4, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4 },
  value: { fontSize: 12, fontWeight: '700', color: '#1A1A1A', width: 64, textAlign: 'right' },
  total: { fontSize: 11, fontWeight: '400', color: '#6B7280' },
});
