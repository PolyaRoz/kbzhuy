import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '../agent';
import { deviationsApi, DeviationRegister } from '../deviations';
import { prepTasksApi } from '../prepTasks';

const PREP_TASKS_KEY = ['prep-tasks', 'today'] as const;
const DEVIATIONS_KEY = ['deviations', 'planned'] as const;

// ---------- Agent chat ----------

export function useAgentChat() {
  return useMutation({
    mutationFn: ({ message, history }: { message: string; history?: { role: 'user' | 'assistant'; content: string }[] }) =>
      agentApi.chat(message, history),
  });
}

export function useAgentAdapt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ reason, kcal_extra }: { reason: string; kcal_extra?: number }) =>
      agentApi.adapt(reason, kcal_extra),
    onSuccess: () => {
      // After plan adaptation, invalidate plan and containers
      qc.invalidateQueries({ queryKey: ['plan'] });
    },
  });
}

// ---------- Deviations ----------

export function usePlannedDeviations() {
  return useQuery({
    queryKey: DEVIATIONS_KEY,
    queryFn: deviationsApi.getPlanned,
    staleTime: 60_000 * 5,
  });
}

export function useRegisterDeviation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DeviationRegister) => deviationsApi.register(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: DEVIATIONS_KEY });
    },
  });
}

export function useRecalcAfterDeviation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (deviation_id: number) => deviationsApi.recalc(deviation_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['plan'] });
    },
  });
}

// ---------- Prep tasks ----------

export function usePrepTasksToday() {
  return useQuery({
    queryKey: PREP_TASKS_KEY,
    queryFn: prepTasksApi.getToday,
    staleTime: 60_000 * 5,
  });
}

export function useMarkPrepTaskDone() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: number) => prepTasksApi.markDone(taskId),
    onMutate: async (taskId) => {
      await qc.cancelQueries({ queryKey: PREP_TASKS_KEY });
      const prev = qc.getQueryData(PREP_TASKS_KEY);
      qc.setQueryData(PREP_TASKS_KEY, (old: any[]) =>
        old?.map((t) => (t.id === taskId ? { ...t, status: 'done' } : t)) ?? []
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      qc.setQueryData(PREP_TASKS_KEY, ctx?.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: PREP_TASKS_KEY });
    },
  });
}
