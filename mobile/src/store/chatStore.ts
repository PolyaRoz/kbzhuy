import { create } from 'zustand';
import { Platform } from 'react-native';

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
};

const KEY = 'chat_history_v1';

const chatStorage = {
  async load(): Promise<ChatMessage[] | null> {
    try {
      let raw: string | null = null;
      if (Platform.OS === 'web') {
        raw = localStorage.getItem(KEY);
      } else {
        const AsyncStorage = require('@react-native-async-storage/async-storage').default;
        raw = await AsyncStorage.getItem(KEY);
      }
      return raw ? (JSON.parse(raw) as ChatMessage[]) : null;
    } catch {
      return null;
    }
  },
  async save(messages: ChatMessage[]) {
    try {
      const serialised = JSON.stringify(messages);
      if (Platform.OS === 'web') {
        localStorage.setItem(KEY, serialised);
      } else {
        const AsyncStorage = require('@react-native-async-storage/async-storage').default;
        await AsyncStorage.setItem(KEY, serialised);
      }
    } catch {
      /* swallow — chat history is non-critical */
    }
  },
  async clear() {
    try {
      if (Platform.OS === 'web') {
        localStorage.removeItem(KEY);
      } else {
        const AsyncStorage = require('@react-native-async-storage/async-storage').default;
        await AsyncStorage.removeItem(KEY);
      }
    } catch {
      /* ignore */
    }
  },
};

interface ChatState {
  messages: ChatMessage[];
  hydrated: boolean;
  hydrate: () => Promise<void>;
  append: (msg: ChatMessage) => void;
  reset: (initial: ChatMessage[]) => Promise<void>;
  clear: () => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  hydrated: false,

  hydrate: async () => {
    if (get().hydrated) return;
    const stored = await chatStorage.load();
    set({ messages: stored ?? [], hydrated: true });
  },

  append: (msg) => {
    const next = [...get().messages, msg];
    set({ messages: next });
    void chatStorage.save(next);
  },

  reset: async (initial) => {
    set({ messages: initial });
    await chatStorage.save(initial);
  },

  clear: async () => {
    set({ messages: [] });
    await chatStorage.clear();
  },
}));
