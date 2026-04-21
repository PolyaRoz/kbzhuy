import { create } from 'zustand';
import { storageApi } from '@/api/storage';

interface Container {
  id: number;
  label: string;
  status: string;
  contents_description: string | null;
  expiry_date: string | null;
  kbzhu: Record<string, number> | null;
  location_id: number;
}

interface StorageLocation {
  id: number;
  name: string;
  location_type: string;
  containers: Container[];
}

interface StorageState {
  locations: StorageLocation[];
  expiring: Container[];
  loading: boolean;
  error: string | null;
  fetchAll: () => Promise<void>;
  fetchExpiring: () => Promise<void>;
}

export const useStorageStore = create<StorageState>((set) => ({
  locations: [],
  expiring: [],
  loading: false,
  error: null,

  fetchAll: async () => {
    set({ loading: true, error: null });
    try {
      const data = await storageApi.getAll();
      set({ locations: data });
    } catch (e: any) {
      set({ error: e?.message ?? 'Ошибка загрузки хранилища' });
    } finally {
      set({ loading: false });
    }
  },

  fetchExpiring: async () => {
    try {
      const data = await storageApi.getExpiring(3);
      set({ expiring: data });
    } catch {
      // Non-critical — expiring list stays empty
    }
  },
}));
