import { create } from 'zustand';
import { storageApi } from '@/api/storage';

export interface InventoryItem {
  id: number;
  name: string;
  category: string;
  quantity: number;
  unit: string;
}

export interface StorageLocation {
  id: number;
  type: 'fridge' | 'freezer' | 'pantry';
  name: string;
  items: InventoryItem[];
}

interface StorageState {
  locations: StorageLocation[];
  loading: boolean;
  error: string | null;
  fetchAll: () => Promise<void>;
  addItem: (payload: { name: string; quantity: number; unit: string; location_type: string; category?: string | null }) => Promise<void>;
  useItem: (itemId: number, quantity: number) => Promise<void>;
  deleteItem: (itemId: number) => Promise<void>;
  clearLocation: (locationType?: 'fridge' | 'freezer' | 'pantry') => Promise<void>;
}

export const useStorageStore = create<StorageState>((set, get) => ({
  locations: [],
  loading: false,
  error: null,

  fetchAll: async () => {
    set({ loading: true, error: null });
    try {
      const data = await storageApi.getAll();
      set({ locations: data.locations ?? [] });
    } catch (e: any) {
      set({ error: e?.message ?? 'Ошибка загрузки хранения' });
    } finally {
      set({ loading: false });
    }
  },

  addItem: async (payload) => {
    await storageApi.addItem(payload);
    await get().fetchAll();
  },

  useItem: async (itemId, quantity) => {
    await storageApi.useItem(itemId, quantity);
    await get().fetchAll();
  },

  deleteItem: async (itemId) => {
    await storageApi.deleteItem(itemId);
    await get().fetchAll();
  },

  clearLocation: async (locationType) => {
    await storageApi.clearLocation(locationType);
    await get().fetchAll();
  },
}));
