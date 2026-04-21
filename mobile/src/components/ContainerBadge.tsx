import { StyleSheet, Text, View } from 'react-native';

const PRIMARY = '#1A7340';
const BLUE = '#2563EB';

interface Props {
  label: string;
  size?: 'sm' | 'md' | 'lg';
  blue?: boolean;
  done?: boolean;
}

const SIZE = {
  sm: { box: 36, radius: 10, font: 13, border: 1.5 },
  md: { box: 44, radius: 12, font: 16, border: 1.5 },
  lg: { box: 52, radius: 14, font: 20, border: 2 },
};

export function ContainerBadge({ label, size = 'md', blue = false, done = false }: Props) {
  const d = SIZE[size];
  const color = done ? '#6EE7B7' : blue ? BLUE : PRIMARY;
  const bg = done ? '#D1FAE5' : blue ? '#DBEAFE' : '#D1FAE5';
  const textColor = done ? '#065F46' : blue ? BLUE : PRIMARY;

  return (
    <View style={[s.badge, { width: d.box, height: d.box, borderRadius: d.radius, backgroundColor: bg, borderWidth: d.border, borderColor: color }]}>
      <Text style={[s.text, { fontSize: d.font, color: textColor }]}>{done ? '✓' : label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  badge: { alignItems: 'center', justifyContent: 'center' },
  text: { fontWeight: '900' },
});
