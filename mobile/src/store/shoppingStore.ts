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
  confirmItems: (itemIds: number[]) => Promise<void>;
  markAllBought: () => Promise<void>;
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

  confirmItems: async (itemIds) => {
    if (!itemIds.length) return;
    set({ loading: true, error: null });
    try {
      await shoppingApi.confirmItems(itemIds);
      await get().fetchList();
    } catch (e: any) {
      set({ error: e?.message ?? 'Не удалось подтвердить покупку' });
    } finally {
      set({ loading: false });
    }
  },

  markAllBought: async () => {
    set({ loading: true, error: null });
    try {
      await shoppingApi.markAll();
      await get().fetchList();
    } catch (e: any) {
      set({ error: e?.message ?? 'Ошибка обновления списка покупок' });
    } finally {
      set({ loading: false });
    }
  },
}));
