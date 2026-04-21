import { create } from 'zustand';
import { shoppingApi } from '@/api/shopping';

export interface ShoppingItem {
  id: number;
  name: string;
  quantity: string;
  unit: string;
  category: string;
  at_home: boolean;
  checked: boolean;
  priority: number;
}

interface ShoppingState {
  items: ShoppingItem[];
  loading: boolean;
  error: string | null;
  fetchList: () => Promise<void>;
  toggleItem: (itemId: number) => Promise<void>;
}

export const useShoppingStore = create<ShoppingState>((set, get) => ({
  items: [],
  loading: false,
  error: null,

  fetchList: async () => {
    set({ loading: true, error: null });
    try {
      const data = await shoppingApi.getList();
      set({ items: data.items ?? [] });
    } catch (e: any) {
      set({ error: e?.message ?? 'Ошибка загрузки списка покупок' });
    } finally {
      set({ loading: false });
    }
  },

  toggleItem: async (itemId) => {
    const item = get().items.find((i) => i.id === itemId);
    if (!item) return;
    const checked = !item.checked;
    // Optimistic update
    set({ items: get().items.map((i) => i.id === itemId ? { ...i, checked } : i) });
    try {
      await shoppingApi.checkItem(itemId, checked);
    } catch {
      // Rollback on failure
      set({ items: get().items.map((i) => i.id === itemId ? { ...i, checked: !checked } : i) });
    }
  },
}));
