import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { planApi } from '../plan';
import { containersApi } from '../containers';

export const PLAN_KEY = ['plan', 'current'] as const;
export const CONTAINERS_TODAY_KEY = ['containers', 'today'] as const;

export function useCurrentPlan() {
  return useQuery({
    queryKey: PLAN_KEY,
    queryFn: planApi.getCurrent,
    staleTime: 60_000,
    retry: false,
  });
}

export function useContainersToday() {
  return useQuery({
    queryKey: CONTAINERS_TODAY_KEY,
    queryFn: containersApi.getToday,
    staleTime: 30_000,
  });
}

export function useMarkEaten() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: containersApi.markEaten,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CONTAINERS_TODAY_KEY });
      qc.invalidateQueries({ queryKey: PLAN_KEY });
    },
  });
}

export function useGeneratePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (notes?: string) => planApi.generate({ use_ai: true, notes }),
    onSuccess: () => qc.invalidateQueries({ queryKey: PLAN_KEY }),
  });
}
