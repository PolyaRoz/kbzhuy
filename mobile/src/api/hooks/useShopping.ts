import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { shoppingApi } from '../shopping';

export const SHOPPING_KEY = ['shopping'] as const;

export function useShoppingList() {
  return useQuery({
    queryKey: SHOPPING_KEY,
    queryFn: shoppingApi.getList,
    staleTime: 30_000,
  });
}

export function useCheckItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, checked }: { itemId: number; checked: boolean }) =>
      shoppingApi.checkItem(itemId, checked),
    onMutate: async ({ itemId, checked }) => {
      await qc.cancelQueries({ queryKey: SHOPPING_KEY });
      const prev = qc.getQueryData(SHOPPING_KEY);
      qc.setQueryData(SHOPPING_KEY, (old: any) => ({
        ...old,
        items: old?.items?.map((i: any) => i.id === itemId ? { ...i, checked } : i) ?? [],
      }));
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(SHOPPING_KEY, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: SHOPPING_KEY }),
  });
}
