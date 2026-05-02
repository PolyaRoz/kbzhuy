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
import { useState, useRef } from 'react';
import { router } from 'expo-router';
import { agentApi } from '@/api/agent';
import { usePlanStore } from '@/store/planStore';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
};

const QUICK_ACTIONS = [
  { id: 'pizza', label: '🍕 Съел не по плану', message: 'Я съел пиццу (2 куска, ~600 ккал). Перестрой остаток дня.' },
  { id: 'today', label: '📋 Что у меня сегодня?', message: 'Покажи мой план питания на сегодня.' },
  { id: 'expiring', label: '⏰ Что скоро испортится?', message: 'Что у меня скоро испортится?' },
  { id: 'simplify', label: '🔄 Упрости меню', message: 'Упрости моё меню — хочу что-то попроще на этой неделе.' },
];

const WELCOME_MSG: Message = {
  id: 'welcome',
  role: 'assistant',
  text: 'Привет! Я твой персональный нутрициолог 🥗\n\nМогу помочь с планом, объяснить что и когда есть, и скорректировать рацион если что-то пошло не так.\n\nЧто хочешь узнать?',
};

const ONBOARDING_MSG: Message = {
  id: 'onboarding',
  role: 'assistant',
  text: 'Привет! 👋 Я — КБЖУЙ, твой нутрициолог.\n\nЯ составлю план питания на неделю, посчитаю КБЖУ под твои цели и скажу что и когда готовить.\n\nС чего начнём?',
};

export default function AgentScreen() {
  const plan = usePlanStore((s) => s.plan);
  const hasFetchedCurrent = usePlanStore((s) => s.hasFetchedCurrent);

  // Show onboarding flow until the user has a plan
  const isOnboarding = hasFetchedCurrent && !plan;

  const [messages, setMessages] = useState<Message[]>([isOnboarding ? ONBOARDING_MSG : WELCOME_MSG]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = { id: Date.now().toString(), role: 'user', text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    const history = messages.slice(-10).map((m) => ({
      role: m.role,
      content: m.text,
    }));

    try {
      const { reply } = await agentApi.chat(text, history);
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: reply,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: 'assistant', text: 'Ошибка соединения. Проверь интернет.' },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  const handleOnboardingAction = (action: 'plan' | 'storage') => {
    if (action === 'plan') {
      router.replace('/(tabs)/plan');
    } else {
      router.replace('/(tabs)/storage');
    }
  };

  // Show onboarding action cards only on the first message (no user input yet)
  const showOnboardingCards = isOnboarding && messages.length === 1;
  // Show regular quick chips for returning users with no additional messages
  const showQuickChips = !isOnboarding && messages.length <= 1;

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {/* Header */}
        <View style={s.header}>
          <View style={s.headerIcon}>
            <Text style={s.headerIconText}>🤖</Text>
          </View>
          <View>
            <Text style={s.headerTitle}>Агент КБЖУЙ</Text>
            <Text style={s.headerSub}>Персональный нутрициолог</Text>
          </View>
          <View style={s.onlineDot} />
        </View>

        {/* Messages */}
        <ScrollView
          ref={scrollRef}
          style={s.messages}
          contentContainerStyle={s.messagesContent}
          showsVerticalScrollIndicator={false}
        >
          {messages.map((msg) => (
            <View key={msg.id} style={[s.bubble, msg.role === 'user' ? s.bubbleUser : s.bubbleAssistant]}>
              {msg.role === 'assistant' && (
                <View style={s.botAvatar}>
                  <Text style={s.botAvatarText}>🤖</Text>
                </View>
              )}
              <View style={[s.bubbleContent, msg.role === 'user' ? s.bubbleContentUser : s.bubbleContentAssistant]}>
                <Text style={[s.bubbleText, msg.role === 'user' && s.bubbleTextUser]}>{msg.text}</Text>
              </View>
            </View>
          ))}

          {loading && (
            <View style={[s.bubble, s.bubbleAssistant]}>
              <View style={s.botAvatar}>
                <Text style={s.botAvatarText}>🤖</Text>
              </View>
              <View style={s.bubbleContentAssistant}>
                <View style={s.typingRow}>
                  <View style={[s.typingDot, { opacity: 0.4 }]} />
                  <View style={[s.typingDot, { opacity: 0.7 }]} />
                  <View style={s.typingDot} />
                </View>
              </View>
            </View>
          )}

          {/* Onboarding action cards — shown as part of message flow */}
          {showOnboardingCards && (
            <View style={s.onboardingCards}>
              <TouchableOpacity
                style={s.onboardingCard}
                onPress={() => handleOnboardingAction('plan')}
                activeOpacity={0.85}
              >
                <Text style={s.onboardingCardEmoji}>📋</Text>
                <View style={s.onboardingCardBody}>
                  <Text style={s.onboardingCardTitle}>Создать план питания</Text>
                  <Text style={s.onboardingCardHint}>Меню на неделю, список покупок и план готовки</Text>
                </View>
                <Text style={s.onboardingCardArrow}>→</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={s.onboardingCard}
                onPress={() => handleOnboardingAction('storage')}
                activeOpacity={0.85}
              >
                <Text style={s.onboardingCardEmoji}>📦</Text>
                <View style={s.onboardingCardBody}>
                  <Text style={s.onboardingCardTitle}>Добавить продукты</Text>
                  <Text style={s.onboardingCardHint}>Сначала укажу что уже есть дома</Text>
                </View>
                <Text style={s.onboardingCardArrow}>→</Text>
              </TouchableOpacity>
            </View>
          )}
        </ScrollView>

        {/* Regular quick chips for existing users */}
        {showQuickChips && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.quickScroll} contentContainerStyle={s.quickRow}>
            {QUICK_ACTIONS.map((qa) => (
              <TouchableOpacity key={qa.id} style={s.quickChip} onPress={() => sendMessage(qa.message)} activeOpacity={0.7}>
                <Text style={s.quickChipText}>{qa.label}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}

        {/* Input */}
        <View style={s.inputRow}>
          <TextInput
            style={s.input}
            value={input}
            onChangeText={setInput}
            placeholder="Напиши агенту..."
            placeholderTextColor={GRAY}
            multiline
            maxLength={500}
            returnKeyType="send"
            onSubmitEditing={() => sendMessage(input)}
          />
          <TouchableOpacity
            style={[s.sendBtn, (!input.trim() || loading) && s.sendBtnDisabled]}
            onPress={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            activeOpacity={0.8}
          >
            {loading ? (
              <ActivityIndicator color="#FFF" size="small" />
            ) : (
              <Text style={s.sendBtnText}>↑</Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}


const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: CARD,
    borderBottomWidth: 1,
    borderBottomColor: '#D4DAD5',
  },
  headerIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#E8E4D9',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerIconText: { fontSize: 20, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  headerTitle: { fontSize: 15, fontWeight: '700', color: BLACK, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3 },
  headerSub: { fontSize: 11, color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  onlineDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#5A7A5C',
    marginLeft: 'auto',
  },

  messages: { flex: 1 },
  messagesContent: { padding: 16, gap: 10 },

  bubble: { flexDirection: 'row', gap: 8, alignItems: 'flex-end' },
  bubbleUser: { flexDirection: 'row-reverse' },
  bubbleAssistant: {},
  botAvatar: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#D1FAE5',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  botAvatarText: { fontSize: 14, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  bubbleContent: { maxWidth: '80%', borderRadius: 16, padding: 12 },
  bubbleContentUser: {
    backgroundColor: PRIMARY,
    borderBottomRightRadius: 4,
  },
  bubbleContentAssistant: {
    backgroundColor: CARD,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: '#D4DAD5',
  },
  bubbleText: { fontSize: 14, color: BLACK, lineHeight: 20, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  bubbleTextUser: { color: '#FFF' },

  typingRow: { flexDirection: 'row', gap: 4, padding: 4 },
  typingDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: PRIMARY,
  },

  // Onboarding action cards
  onboardingCards: { gap: 10, marginTop: 4, marginLeft: 38 },
  onboardingCard: {
    backgroundColor: CARD,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#D4DAD5',
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  onboardingCardEmoji: { fontSize: 28 },
  onboardingCardBody: { flex: 1 },
  onboardingCardTitle: { fontSize: 15, fontWeight: '800', color: BLACK, marginBottom: 3, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", letterSpacing: -0.3 },
  onboardingCardHint: { fontSize: 12, color: GRAY, lineHeight: 17, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  onboardingCardArrow: { fontSize: 18, color: PRIMARY, fontWeight: '700' },

  quickScroll: { maxHeight: 52 },
  quickRow: { paddingHorizontal: 16, gap: 8, paddingVertical: 10 },
  quickChip: {
    backgroundColor: CARD,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderWidth: 1,
    borderColor: '#D1FAE5',
  },
  quickChipText: { fontSize: 12, color: PRIMARY, fontWeight: '600', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },

  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    padding: 12,
    backgroundColor: CARD,
    borderTopWidth: 1,
    borderTopColor: '#D4DAD5',
  },
  input: {
    flex: 1,
    backgroundColor: '#F9FAFB',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    color: BLACK,
    maxHeight: 100,
    borderWidth: 1,
    borderColor: '#D4DAD5',
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: PRIMARY,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendBtnText: { color: '#FFF', fontSize: 20, fontWeight: '700', lineHeight: 22, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
});
