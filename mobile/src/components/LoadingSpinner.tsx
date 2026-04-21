import { ActivityIndicator, StyleSheet, View } from 'react-native';

const PRIMARY = '#1A7340';

export function LoadingSpinner() {
  return (
    <View style={s.wrap}>
      <ActivityIndicator size="large" color={PRIMARY} />
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
