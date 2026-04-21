import { StyleSheet, Text, View } from 'react-native';

interface Props {
  emoji?: string;
  title: string;
  desc?: string;
}

export function EmptyState({ emoji = '📭', title, desc }: Props) {
  return (
    <View style={s.wrap}>
      <Text style={s.emoji}>{emoji}</Text>
      <Text style={s.title}>{title}</Text>
      {desc && <Text style={s.desc}>{desc}</Text>}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { alignItems: 'center', paddingVertical: 48, paddingHorizontal: 24 },
  emoji: { fontSize: 48, marginBottom: 12 },
  title: { fontSize: 17, fontWeight: '700', color: '#1A1A1A', textAlign: 'center', marginBottom: 6 },
  desc: { fontSize: 14, color: '#6B7280', textAlign: 'center', lineHeight: 20 },
});
