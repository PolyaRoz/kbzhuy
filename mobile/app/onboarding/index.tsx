import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useAuthStore } from '@/store/authStore';

const PRIMARY = '#1A7340';
const BG = '#F6FAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6B7280';
const BORDER = '#E5E7EB';
const DANGER = '#DC2626';

type Mode = 'login' | 'register';

export default function OnboardingEntryScreen() {
  const login = useAuthStore((state) => state.login);
  const register = useAuthStore((state) => state.register);

  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    const trimmedEmail = email.trim().toLowerCase();
    const trimmedPassword = password.trim();

    setError('');
    if (!trimmedEmail || !trimmedPassword) {
      setError('Введите email и пароль.');
      return;
    }

    if (mode === 'register' && trimmedPassword.length < 6) {
      setError('Пароль должен быть не короче 6 символов.');
      return;
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        await login(trimmedEmail, trimmedPassword);
        const { onboardingCompleted } = useAuthStore.getState();
        router.replace(onboardingCompleted ? '/(tabs)' : '/onboarding/step1');
      } else {
        await register(trimmedEmail, trimmedPassword);
        router.replace('/onboarding/step1');
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setError(
        detail === 'Invalid credentials'
          ? 'Неверный email или пароль.'
          : detail === 'Email already registered'
            ? 'Аккаунт с таким email уже существует.'
            : detail || 'Не удалось выполнить вход.',
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={s.container} keyboardShouldPersistTaps="handled">
          <Text style={s.title}>КБЖУЙ</Text>
          <Text style={s.sub}>
            Можно войти в существующий аккаунт или создать новый. Для нового аккаунта после этого откроется анкета.
          </Text>

          <View style={s.modeRow}>
            <TouchableOpacity
              style={[s.modeButton, mode === 'login' && s.modeButtonActive]}
              onPress={() => setMode('login')}
              activeOpacity={0.8}
            >
              <Text style={[s.modeText, mode === 'login' && s.modeTextActive]}>Войти</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[s.modeButton, mode === 'register' && s.modeButtonActive]}
              onPress={() => setMode('register')}
              activeOpacity={0.8}
            >
              <Text style={[s.modeText, mode === 'register' && s.modeTextActive]}>Регистрация</Text>
            </TouchableOpacity>
          </View>

          <View style={s.card}>
            <Text style={s.sectionTitle}>{mode === 'login' ? 'Вход' : 'Создать аккаунт'}</Text>
            <TextInput
              style={s.input}
              placeholder="Email"
              placeholderTextColor={GRAY}
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TextInput
              style={s.input}
              placeholder="Пароль"
              placeholderTextColor={GRAY}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
            />
            {mode === 'register' && (
              <Text style={s.hint}>После регистрации откроется пошаговая анкета профиля.</Text>
            )}
            {!!error && <Text style={s.error}>{error}</Text>}
            <TouchableOpacity style={s.primaryButton} onPress={handleSubmit} disabled={loading} activeOpacity={0.85}>
              {loading ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryButtonText}>{mode === 'login' ? 'Войти' : 'Продолжить'}</Text>}
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  container: { flexGrow: 1, padding: 24, justifyContent: 'center' },
  title: { fontSize: 32, fontWeight: '800', color: BLACK, marginBottom: 8 },
  sub: { fontSize: 15, color: GRAY, marginBottom: 24, lineHeight: 22 },
  modeRow: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  modeButton: {
    flex: 1,
    backgroundColor: CARD,
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: BORDER,
    paddingVertical: 14,
    alignItems: 'center',
  },
  modeButtonActive: { borderColor: PRIMARY, backgroundColor: '#F0FDF4' },
  modeText: { fontSize: 15, fontWeight: '700', color: GRAY },
  modeTextActive: { color: PRIMARY },
  card: {
    backgroundColor: CARD,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: BORDER,
    padding: 18,
  },
  sectionTitle: { fontSize: 18, fontWeight: '800', color: BLACK, marginBottom: 14 },
  input: {
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: BORDER,
    paddingHorizontal: 14,
    paddingVertical: 14,
    fontSize: 15,
    color: BLACK,
    marginBottom: 10,
  },
  hint: { fontSize: 13, color: GRAY, marginTop: 2, marginBottom: 6 },
  error: { fontSize: 13, color: DANGER, marginBottom: 10 },
  primaryButton: {
    marginTop: 6,
    backgroundColor: PRIMARY,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 15,
  },
  primaryButtonText: { fontSize: 16, fontWeight: '800', color: '#FFF' },
});
