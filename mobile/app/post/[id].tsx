import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { trayApi, TrayPost, TrayComment } from '@/api/tray';
import { CATEGORY_META } from '../(tabs)/tray';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';
const BORDER = '#D4DAD5';

function formatDate(iso: string | null) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'только что';
  if (diffMin < 60) return `${diffMin} мин назад`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} ч назад`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay} дн назад`;
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`;
}

export default function PostDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const postId = Number(id);
  const [post, setPost] = useState<TrayPost | null>(null);
  const [comments, setComments] = useState<TrayComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [commentText, setCommentText] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!postId) return;
    setLoading(true);
    try {
      const [p, c] = await Promise.all([trayApi.get(postId), trayApi.listComments(postId)]);
      setPost(p);
      setComments(c.items ?? []);
    } catch {
      setPost(null);
    } finally {
      setLoading(false);
    }
  }, [postId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleLike = async () => {
    if (!post) return;
    setPost({ ...post, liked_by_me: !post.liked_by_me, like_count: post.like_count + (post.liked_by_me ? -1 : 1) });
    try {
      const res = await trayApi.toggleLike(post.id);
      setPost((p) => (p ? { ...p, liked_by_me: res.liked, like_count: res.like_count } : p));
    } catch {
      setPost((p) =>
        p ? { ...p, liked_by_me: !p.liked_by_me, like_count: p.like_count + (p.liked_by_me ? -1 : 1) } : p,
      );
    }
  };

  const handleComment = async () => {
    const text = commentText.trim();
    if (!text || !post || submitting) return;
    setSubmitting(true);
    try {
      const newComment = await trayApi.addComment(post.id, text);
      setComments((prev) => [...prev, newComment]);
      setCommentText('');
      setPost((p) => (p ? { ...p, comment_count: p.comment_count + 1 } : p));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteComment = async (commentId: number) => {
    if (!post) return;
    if (typeof window !== 'undefined' && !window.confirm('Удалить комментарий?')) return;
    try {
      await trayApi.deleteComment(post.id, commentId);
      setComments((prev) => prev.filter((c) => c.id !== commentId));
      setPost((p) => (p ? { ...p, comment_count: Math.max(0, p.comment_count - 1) } : p));
    } catch {
      // ignore
    }
  };

  const handleDeletePost = async () => {
    if (!post) return;
    if (typeof window !== 'undefined' && !window.confirm('Удалить пост?')) return;
    try {
      await trayApi.remove(post.id);
      router.back();
    } catch {
      // ignore
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.headerBar}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
            <Ionicons name="arrow-back" size={22} color={BLACK} />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Пост</Text>
          <View style={{ width: 36 }} />
        </View>
        <ActivityIndicator color={PRIMARY} style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }

  if (!post) {
    return (
      <SafeAreaView style={s.safe}>
        <View style={s.headerBar}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
            <Ionicons name="arrow-back" size={22} color={BLACK} />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Пост</Text>
          <View style={{ width: 36 }} />
        </View>
        <View style={s.emptyWrap}>
          <Text style={s.emptyText}>Пост не найден</Text>
        </View>
      </SafeAreaView>
    );
  }

  const meta = CATEGORY_META[post.category];

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={s.headerBar}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn} activeOpacity={0.7}>
            <Ionicons name="arrow-back" size={22} color={BLACK} />
          </TouchableOpacity>
          <Text style={s.headerTitle} numberOfLines={1}>
            Пост
          </Text>
          <View style={{ width: 36 }} />
        </View>

        <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
          {post.image_url ? (
            <Image source={{ uri: post.image_url }} style={s.image} resizeMode="cover" />
          ) : null}

          <View style={s.body}>
            <View style={[s.catBadge, { backgroundColor: `${meta.color}15`, borderColor: `${meta.color}40` }]}>
              <Ionicons name={meta.icon as any} size={10} color={meta.color} />
              <Text style={[s.catBadgeText, { color: meta.color }]}>
                {meta.label}
              </Text>
            </View>

            <Text style={s.title}>{post.title}</Text>

            <View style={s.authorRow}>
              <Text style={s.author}>@{post.author.name}</Text>
              <Text style={s.dot}>·</Text>
              <Text style={s.date}>{formatDate(post.created_at)}</Text>
            </View>

            {post.text ? <Text style={s.text}>{post.text}</Text> : null}

            <View style={s.actionsRow}>
              <TouchableOpacity style={s.actionBtn} onPress={handleLike} activeOpacity={0.7}>
                <Ionicons
                  name={post.liked_by_me ? 'heart' : 'heart-outline'}
                  size={22}
                  color={post.liked_by_me ? '#E5484D' : GRAY}
                />
                <Text style={[s.actionText, post.liked_by_me && { color: '#E5484D' }]}>{post.like_count}</Text>
              </TouchableOpacity>
              <View style={s.actionBtn}>
                <Ionicons name="chatbubble-outline" size={20} color={GRAY} />
                <Text style={s.actionText}>{post.comment_count}</Text>
              </View>
            </View>
          </View>

          <Text style={s.commentsTitle}>Комментарии</Text>

          {comments.length === 0 ? (
            <Text style={s.noComments}>Пока нет комментариев — будь первым.</Text>
          ) : (
            <View style={s.commentList}>
              {comments.map((c) => (
                <View key={c.id} style={s.comment}>
                  <View style={s.commentHeader}>
                    <Text style={s.commentAuthor}>@{c.author.name}</Text>
                    <Text style={s.commentDate}>{formatDate(c.created_at)}</Text>
                    {c.is_mine && (
                      <TouchableOpacity onPress={() => handleDeleteComment(c.id)} hitSlop={8} style={{ marginLeft: 'auto' }}>
                        <Ionicons name="trash-outline" size={14} color="#C8553D" />
                      </TouchableOpacity>
                    )}
                  </View>
                  <Text style={s.commentText}>{c.text}</Text>
                </View>
              ))}
            </View>
          )}

          <View style={{ height: 16 }} />
        </ScrollView>

        <View style={s.commentInputRow}>
          <TextInput
            style={s.commentInput}
            placeholder="Написать комментарий..."
            placeholderTextColor={GRAY}
            value={commentText}
            onChangeText={setCommentText}
            multiline
            maxLength={2000}
          />
          <TouchableOpacity
            style={[s.sendBtn, (!commentText.trim() || submitting) && s.sendBtnDisabled]}
            onPress={handleComment}
            disabled={!commentText.trim() || submitting}
            activeOpacity={0.8}
          >
            {submitting ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.sendBtnText}>↑</Text>}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  headerBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: CARD,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
  },
  backBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 16,
    fontWeight: '800',
    color: BLACK,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  content: { paddingBottom: 20 },
  image: { width: '100%', height: 220, backgroundColor: '#F0EEE7' },
  body: { padding: 16, gap: 10 },
  catBadge: {
    alignSelf: 'flex-start',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  catBadgeText: { fontSize: 11, fontWeight: '800', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  title: {
    fontSize: 22,
    fontWeight: '900',
    color: BLACK,
    lineHeight: 28,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
    letterSpacing: -0.44,
  },
  authorRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  author: { fontSize: 13, color: PRIMARY, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  dot: { color: GRAY, fontSize: 12 },
  date: { color: GRAY, fontSize: 12, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  text: { fontSize: 14, color: BLACK, lineHeight: 22, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif", marginTop: 4 },
  actionsRow: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#F0EEE7',
  },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  actionText: { fontSize: 14, color: GRAY, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  commentsTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: BLACK,
    paddingHorizontal: 16,
    marginTop: 8,
    marginBottom: 8,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  noComments: { color: GRAY, fontSize: 13, paddingHorizontal: 16, fontStyle: 'italic', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  commentList: { paddingHorizontal: 16, gap: 8 },
  comment: { backgroundColor: CARD, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: BORDER },
  commentHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  commentAuthor: { fontSize: 12, fontWeight: '800', color: PRIMARY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  commentDate: { fontSize: 11, color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  commentText: { fontSize: 13, color: BLACK, lineHeight: 19, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  commentInputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    padding: 12,
    backgroundColor: CARD,
    borderTopWidth: 1,
    borderTopColor: BORDER,
  },
  commentInput: {
    flex: 1,
    backgroundColor: '#F9FAFB',
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 13,
    color: BLACK,
    maxHeight: 100,
    borderWidth: 1,
    borderColor: BORDER,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  sendBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: PRIMARY,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendBtnText: { color: '#FFF', fontSize: 18, fontWeight: '700' },
  emptyWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  emptyText: { fontSize: 16, color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
});
