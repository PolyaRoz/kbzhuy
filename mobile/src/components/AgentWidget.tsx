import { Ionicons } from '@expo/vector-icons';
import { useRef, useState } from 'react';
import {
  ActivityIndicator,
  Dimensions,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { agentApi } from '@/api/agent';

const PRIMARY = '#2B3A2E';
const BLUE = '#4A5C4D';
const CARD = '#FFFFFF';
const BG = '#FAFAF7';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';

type Message = { id: string; role: 'user' | 'assistant'; text: string };

const WELCOME_MSG: Message = {
  id: 'welcome',
  role: 'assistant',
  text: 'Привет! Чем могу помочь?\n\nСпроси про план, что поесть сейчас, или скажи если что-то пошло не по плану.',
};

const QUICK_ACTIONS = [
  { id: 'today', label: 'Что сегодня?', message: 'Покажи мой план питания на сегодня.' },
  { id: 'offplan', label: 'Съел не по плану', message: 'Я съел что-то не по плану. Помоги скорректировать день.' },
  { id: 'expiring', label: 'Что испортится?', message: 'Что у меня скоро испортится?' },
];

const TAB_BAR_H = Platform.OS === 'ios' ? 84 : 64;
const FAB_SIZE = 52;
const FAB_MARGIN = 16;
const FAB_BOTTOM = TAB_BAR_H + FAB_MARGIN;
const PANEL_BOTTOM = FAB_BOTTOM + FAB_SIZE + 8;

export function AgentWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([WELCOME_MSG]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: Message = { id: Date.now().toString(), role: 'user', text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    const history = messages.slice(-10).map((m) => ({ role: m.role, content: m.text }));
    try {
      const { reply } = await agentApi.chat(text, history);
      setMessages((prev) => [...prev, { id: (Date.now() + 1).toString(), role: 'assistant', text: reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: 'assistant', text: 'Ошибка соединения. Попробуй ещё раз.' },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  const { width, height } = Dimensions.get('window');
  const panelW = Math.min(360, width - 32);
  const panelH = Math.min(500, height - PANEL_BOTTOM - 24);

  return (
    <>
      {/* Chat panel */}
      {open && (
        <View style={[w.panel, { width: panelW, height: panelH, bottom: PANEL_BOTTOM }]}>
          {/* Header */}
          <View style={w.panelHeader}>
            <View style={w.panelAvatar}>
              <Ionicons name="sparkles" size={15} color={PRIMARY} />
            </View>
            <Text style={w.panelTitle}>Агент КБЖУЙ</Text>
            <View style={w.onlineDot} />
            <TouchableOpacity style={w.closeBtn} onPress={() => setOpen(false)} activeOpacity={0.7}>
              <Ionicons name="close" size={16} color={GRAY} />
            </TouchableOpacity>
          </View>

          {/* Messages */}
          <ScrollView
            ref={scrollRef}
            style={{ flex: 1 }}
            contentContainerStyle={w.messagesContent}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          >
            {messages.map((msg) => (
              <View key={msg.id} style={[w.bubble, msg.role === 'user' ? w.bubbleUser : w.bubbleBot]}>
                <View style={[w.bubbleContent, msg.role === 'user' ? w.bubbleContentUser : w.bubbleContentBot]}>
                  <Text style={[w.bubbleText, msg.role === 'user' && w.bubbleTextUser]}>{msg.text}</Text>
                </View>
              </View>
            ))}
            {loading && (
              <View style={w.bubbleBot}>
                <View style={w.bubbleContentBot}>
                  <View style={w.typingRow}>
                    <View style={[w.typingDot, { opacity: 0.3 }]} />
                    <View style={[w.typingDot, { opacity: 0.6 }]} />
                    <View style={w.typingDot} />
                  </View>
                </View>
              </View>
            )}
          </ScrollView>

          {/* Quick actions — only on fresh start */}
          {messages.length <= 1 && (
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={w.quickScroll}
              contentContainerStyle={w.quickRow}
            >
              {QUICK_ACTIONS.map((qa) => (
                <TouchableOpacity key={qa.id} style={w.quickChip} onPress={() => sendMessage(qa.message)} activeOpacity={0.7}>
                  <Text style={w.quickChipText}>{qa.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          )}

          {/* Input */}
          <View style={w.inputRow}>
            <TextInput
              style={w.input}
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
              style={[w.sendBtn, (!input.trim() || loading) && w.sendBtnDisabled]}
              onPress={() => sendMessage(input)}
              disabled={!input.trim() || loading}
              activeOpacity={0.8}
            >
              {loading
                ? <ActivityIndicator color="#FFF" size="small" />
                : <Ionicons name="arrow-up" size={18} color="#FFF" />
              }
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* FAB */}
      <TouchableOpacity
        style={[w.fab, { bottom: FAB_BOTTOM }, open && w.fabOpen]}
        onPress={() => setOpen((v) => !v)}
        activeOpacity={0.85}
      >
        <Ionicons name={open ? 'close' : 'chatbubble-ellipses'} size={24} color="#FFF" />
      </TouchableOpacity>
    </>
  );
}

const w = StyleSheet.create({
  panel: {
    position: 'absolute',
    right: FAB_MARGIN,
    backgroundColor: CARD,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#D4DAD5',
    overflow: 'hidden',
    boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
    zIndex: 100,
  } as any,

  panelHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 11,
    borderBottomWidth: 1,
    borderBottomColor: '#D4DAD5',
  },
  panelAvatar: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#E8E4D9',
    alignItems: 'center',
    justifyContent: 'center',
  },
  panelTitle: {
    flex: 1,
    fontSize: 13,
    fontWeight: '800',
    color: BLACK,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
    letterSpacing: -0.26,
  },
  onlineDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: '#5A7A5C',
  },
  closeBtn: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: '#F0EEE7',
    alignItems: 'center',
    justifyContent: 'center',
  },

  messagesContent: { padding: 12, gap: 6, flexGrow: 1 },

  bubble: { flexDirection: 'row' },
  bubbleUser: { justifyContent: 'flex-end' },
  bubbleBot: {},
  bubbleContent: { maxWidth: '85%', borderRadius: 14, padding: 10 },
  bubbleContentUser: { backgroundColor: PRIMARY, borderBottomRightRadius: 4 },
  bubbleContentBot: {
    backgroundColor: BG,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: '#D4DAD5',
  },
  bubbleText: {
    fontSize: 13,
    color: BLACK,
    lineHeight: 18,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  bubbleTextUser: { color: '#FFF' },

  typingRow: { flexDirection: 'row', gap: 4, padding: 2 },
  typingDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: BLUE },

  quickScroll: { maxHeight: 44, borderTopWidth: 1, borderTopColor: '#F0EEE7' },
  quickRow: { paddingHorizontal: 12, gap: 6, paddingVertical: 8, alignItems: 'center' },
  quickChip: {
    backgroundColor: '#E8E4D9',
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  quickChipText: {
    fontSize: 11,
    color: PRIMARY,
    fontWeight: '700',
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },

  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    padding: 10,
    borderTopWidth: 1,
    borderTopColor: '#D4DAD5',
  },
  input: {
    flex: 1,
    backgroundColor: BG,
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 13,
    color: BLACK,
    maxHeight: 72,
    borderWidth: 1,
    borderColor: '#D4DAD5',
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  sendBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: PRIMARY,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },

  fab: {
    position: 'absolute',
    right: FAB_MARGIN,
    width: FAB_SIZE,
    height: FAB_SIZE,
    borderRadius: FAB_SIZE / 2,
    backgroundColor: PRIMARY,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 101,
    boxShadow: '0 4px 16px rgba(43,58,46,0.35)',
  } as any,
  fabOpen: { backgroundColor: BLUE },
});
