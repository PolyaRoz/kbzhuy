import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { cookingApi } from '../cooking';

export const COOKING_KEY = ['cooking', 'plan'] as const;

export function useCookingPlan() {
  return useQuery({
    queryKey: COOKING_KEY,
    queryFn: cookingApi.getPlan,
    staleTime: 60_000,
    retry: false,
  });
}

export function useMarkStepDone() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: cookingApi.markStepDone,
    onSuccess: () => qc.invalidateQueries({ queryKey: COOKING_KEY }),
  });
}
