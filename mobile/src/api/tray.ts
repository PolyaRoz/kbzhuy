import { apiClient } from './client';

export type PostCategory = 'recipe' | 'lifehack' | 'progress' | 'idea' | 'discussion';

export interface PostAuthor {
  id: number;
  name: string;
}

export interface TrayPost {
  id: number;
  category: PostCategory;
  title: string;
  text: string;
  image_url: string | null;
  created_at: string | null;
  author: PostAuthor;
  like_count: number;
  comment_count: number;
  liked_by_me: boolean;
}

export interface TrayComment {
  id: number;
  text: string;
  created_at: string | null;
  author: PostAuthor;
  is_mine: boolean;
}

export const trayApi = {
  list: (category?: PostCategory, my?: boolean) =>
    apiClient
      .get<{ items: TrayPost[] }>('/tray/posts', {
        params: {
          ...(category ? { category } : {}),
          ...(my ? { my: 'true' } : {}),
        },
      })
      .then((r) => r.data),

  get: (postId: number) =>
    apiClient.get<TrayPost>(`/tray/posts/${postId}`).then((r) => r.data),

  create: (payload: { category: PostCategory; title: string; text: string; image_url?: string | null }) =>
    apiClient.post<TrayPost>('/tray/posts', payload).then((r) => r.data),

  remove: (postId: number) =>
    apiClient.delete(`/tray/posts/${postId}`).then((r) => r.data),

  toggleLike: (postId: number) =>
    apiClient
      .post<{ liked: boolean; like_count: number }>(`/tray/posts/${postId}/like`)
      .then((r) => r.data),

  listComments: (postId: number) =>
    apiClient
      .get<{ items: TrayComment[] }>(`/tray/posts/${postId}/comments`)
      .then((r) => r.data),

  addComment: (postId: number, text: string) =>
    apiClient.post<TrayComment>(`/tray/posts/${postId}/comments`, { text }).then((r) => r.data),

  deleteComment: (postId: number, commentId: number) =>
    apiClient.delete(`/tray/posts/${postId}/comments/${commentId}`).then((r) => r.data),
};
