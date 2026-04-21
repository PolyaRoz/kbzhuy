import { useQuery } from '@tanstack/react-query';
import { storageApi } from '../storage';

export const STORAGE_KEY = ['storage'] as const;
export const EXPIRING_KEY = ['storage', 'expiring'] as const;

export function useStorage() {
  return useQuery({
    queryKey: STORAGE_KEY,
    queryFn: storageApi.getAll,
    staleTime: 60_000,
  });
}

export function useExpiring(days = 3) {
  return useQuery({
    queryKey: [...EXPIRING_KEY, days],
    queryFn: () => storageApi.getExpiring(days),
    staleTime: 60_000,
  });
}
