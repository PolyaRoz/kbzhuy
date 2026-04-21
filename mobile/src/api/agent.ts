import { apiClient } from './client';

export type ChatMessage = { role: 'user' | 'assistant'; content: string };

export type ChatResponse = {
  reply: string;
  tool_calls: { tool: string; result: unknown }[];
  deviation_id: number | null;
};

export const agentApi = {
  chat: (message: string, history?: ChatMessage[]): Promise<ChatResponse> =>
    apiClient.post('/agent/chat', { message, history }).then((r) => r.data),

  adapt: (reason: string, kcal_extra?: number): Promise<ChatResponse> =>
    apiClient.post('/agent/adapt', { reason, kcal_extra }).then((r) => r.data),
};
