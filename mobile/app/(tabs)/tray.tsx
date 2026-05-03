import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { trayApi, TrayPost, PostCategory } from '@/api/tray';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';
const BORDER = '#D4DAD5';

interface CategoryDef {
  key: PostCategory | 'all' | 'mine';
  label: string;
  icon: string | null;
  color: string;
}

const CATEGORIES: CategoryDef[] = [
  { key: 'all',        label: 'Все',          icon: null,                   color: PRIMARY },
  { key: 'recipe',     label: 'Рецепты',      icon: 'restaurant-outline',   color: '#C9A14B' },
  { key: 'lifehack',   label: 'Лайфхаки',     icon: 'flash-outline',        color: '#4A5C4D' },
  { key: 'progress',   label: 'Прогресс',     icon: 'trending-up-outline',  color: '#5A7A5C' },
  { key: 'idea',       label: 'Идеи',         icon: 'bulb-outline',         color: '#C8553D' },
  { key: 'discussion', label: 'Обсуждения',   icon: 'chatbubbles-outline',  color: '#6E7E70' },
  { key: 'mine',       label: 'Мои посты',    icon: 'person-outline',       color: PRIMARY },
];

export const CATEGORY_META: Record<PostCategory, { label: string; icon: string; color: string }> = {
  recipe:     { label: 'Рецепт',      icon: 'restaurant-outline',   color: '#C9A14B' },
  lifehack:   { label: 'Лайфхак',     icon: 'flash-outline',        color: '#4A5C4D' },
  progress:   { label: 'Прогресс',    icon: 'trending-up-outline',  color: '#5A7A5C' },
  idea:       { label: 'Идея',        icon: 'bulb-outline',         color: '#C8553D' },
  discussion: { label: 'Обсуждение',  icon: 'chatbubbles-outline',  color: '#6E7E70' },
};

export default function TrayScreen() {
  const [posts, setPosts] = useState<TrayPost[]>([]);
  const [activeCategory, setActiveCategory] = useState<PostCategory | 'all' | 'mine'>('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchPosts = useCallback(async (category: PostCategory | 'all' | 'mine', refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    try {
      const isMine = category === 'mine';
      const cat = !isMine && category !== 'all' ? (category as PostCategory) : undefined;
      const data = await trayApi.list(cat, isMine);
      setPosts(data.items ?? []);
    } catch {
      setPosts([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchPosts(activeCategory);
  }, [activeCategory, fetchPosts]);

  // Refresh on tab focus to pick up new posts/likes from other users
  useFocusEffect(
    useCallback(() => {
      void fetchPosts(activeCategory, true);
    }, [activeCategory, fetchPosts]),
  );

  const handleLike = async (post: TrayPost) => {
    // Optimistic update
    setPosts((prev) =>
      prev.map((p) =>
        p.id === post.id
          ? { ...p, liked_by_me: !p.liked_by_me, like_count: p.like_count + (p.liked_by_me ? -1 : 1) }
          : p,
      ),
    );
    try {
      const res = await trayApi.toggleLike(post.id);
      setPosts((prev) =>
        prev.map((p) => (p.id === post.id ? { ...p, liked_by_me: res.liked, like_count: res.like_count } : p)),
      );
    } catch {
      // Revert on error
      setPosts((prev) =>
        prev.map((p) =>
          p.id === post.id
            ? { ...p, liked_by_me: post.liked_by_me, like_count: post.like_count }
            : p,
        ),
      );
    }
  };

  return (
    <SafeAreaView style={s.safe}>
      {/* ── fixed header ── */}
      <View style={s.headerRow}>
        <Text style={s.title}>Поднос</Text>
        <View style={s.headerActions}>
          <TouchableOpacity
            style={s.refreshBtn}
            onPress={() => fetchPosts(activeCategory, true)}
            activeOpacity={0.7}
            disabled={refreshing}
          >
            <Ionicons name="refresh" size={18} color={refreshing ? GRAY : PRIMARY} />
          </TouchableOpacity>
          <TouchableOpacity
            style={s.createBtn}
            onPress={() => router.push('/post/create')}
            activeOpacity={0.85}
          >
            <Ionicons name="add" size={18} color="#FFF" />
            <Text style={s.createBtnText}>Пост</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* ── fixed-height category row ── */}
      <View style={s.catWrapper}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={s.catRow}
        >
          {CATEGORIES.map((cat) => {
            const active = cat.key === activeCategory;
            const chipBg = active ? cat.color : `${cat.color}14`;
            const chipBorder = active ? cat.color : `${cat.color}50`;
            const chipTextColor = active ? '#FFF' : cat.color;
            return (
              <TouchableOpacity
                key={cat.key}
                style={[s.catChip, { backgroundColor: chipBg, borderColor: chipBorder }]}
                onPress={() => setActiveCategory(cat.key)}
                activeOpacity={0.8}
              >
                {cat.icon ? (
                  <Ionicons name={cat.icon as any} size={11} color={chipTextColor} />
                ) : null}
                <Text style={[s.catChipText, { color: chipTextColor }]}>
                  {cat.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* ── feed: fills remaining space, top-aligned ── */}
      <View style={s.feedWrapper}>
        {loading && posts.length === 0 ? (
          <ActivityIndicator color={PRIMARY} style={{ marginTop: 40 }} />
        ) : posts.length === 0 ? (
          <View style={s.emptyCard}>
            <Text style={s.emptyText}>Здесь пока пусто</Text>
            <Text style={s.emptyHint}>
              {activeCategory === 'all'
                ? 'Стань первым — поделись рецептом или лайфхаком.'
                : 'В этой категории пока нет постов.'}
            </Text>
          </View>
        ) : (
          <ScrollView
            style={s.feedScroll}
            contentContainerStyle={s.feed}
            showsVerticalScrollIndicator={false}
            refreshing={refreshing}
            onRefresh={() => fetchPosts(activeCategory, true)}
          >
            {posts.map((post) => (
              <PostCard key={post.id} post={post} onLike={() => handleLike(post)} />
            ))}
            <View style={{ height: 24 }} />
          </ScrollView>
        )}
      </View>
    </SafeAreaView>
  );
}

function PostCard({ post, onLike }: { post: TrayPost; onLike: () => void }) {
  const meta = CATEGORY_META[post.category];
  const goToPost = () => router.push(`/post/${post.id}`);

  return (
    <TouchableOpacity style={s.card} onPress={goToPost} activeOpacity={0.92}>
      {post.image_url ? (
        <Image source={{ uri: post.image_url }} style={s.cardImage} resizeMode="cover" />
      ) : null}

      <View style={s.cardBody}>
        <View style={[s.catBadge, { backgroundColor: `${meta.color}15`, borderColor: `${meta.color}40` }]}>
          <Ionicons name={meta.icon as any} size={10} color={meta.color} />
          <Text style={[s.catBadgeText, { color: meta.color }]}>
            {meta.label}
          </Text>
        </View>

        <Text style={s.cardTitle} numberOfLines={2}>
          {post.title}
        </Text>

        {post.text ? (
          <Text style={s.cardText} numberOfLines={3}>
            {post.text}
          </Text>
        ) : null}

        <View style={s.cardFooter}>
          <Text style={s.cardAuthor}>@{post.author.name}</Text>
          <View style={s.cardMeta}>
            <TouchableOpacity
              style={s.metaBtn}
              onPress={(e) => {
                e.stopPropagation();
                onLike();
              }}
              activeOpacity={0.7}
            >
              <Ionicons
                name={post.liked_by_me ? 'heart' : 'heart-outline'}
                size={18}
                color={post.liked_by_me ? '#E5484D' : GRAY}
              />
              <Text style={[s.metaText, post.liked_by_me && { color: '#E5484D' }]}>{post.like_count}</Text>
            </TouchableOpacity>
            <View style={s.metaBtn}>
              <Ionicons name="chatbubble-outline" size={16} color={GRAY} />
              <Text style={s.metaText}>{post.comment_count}</Text>
            </View>
          </View>
        </View>
      </View>
    </TouchableOpacity>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },

  // ── header ──────────────────────────────────────────
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 8,
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    color: BLACK,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
    letterSpacing: -0.44,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  refreshBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: CARD,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: BORDER,
  },
  createBtn: {
    backgroundColor: PRIMARY,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  createBtnText: { color: '#FFF', fontSize: 13, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },

  // ── category row ─────────────────────────────────────
  // Fixed height so the row never shifts when category changes
  catWrapper: {
    height: 52,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
    justifyContent: 'center',
  },
  catRow: {
    paddingHorizontal: 16,
    gap: 8,
    alignItems: 'center',
  },
  catChip: {
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderWidth: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  catChipActive: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  catChipText: { color: GRAY, fontSize: 12, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  catChipTextActive: { color: '#FFF' },

  // ── feed area ─────────────────────────────────────────
  // flex:1 takes all remaining vertical space; content is always top-aligned
  feedWrapper: { flex: 1 },
  feedScroll: { flex: 1 },
  feed: { paddingHorizontal: 16, paddingTop: 12, gap: 12 },
  card: {
    backgroundColor: CARD,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: BORDER,
    overflow: 'hidden',
  },
  cardImage: { width: '100%', height: 180, backgroundColor: '#F0EEE7' },
  cardBody: { padding: 14, gap: 8 },
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
  cardTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: BLACK,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
    letterSpacing: -0.32,
    lineHeight: 22,
  },
  cardText: { fontSize: 13, color: GRAY, lineHeight: 19, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  cardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 4,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#F0EEE7',
  },
  cardAuthor: { fontSize: 12, color: GRAY, fontWeight: '600', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  cardMeta: { flexDirection: 'row', gap: 14 },
  metaBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  metaText: { fontSize: 13, color: GRAY, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  emptyCard: {
    backgroundColor: CARD,
    borderRadius: 16,
    padding: 32,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: BORDER,
    margin: 16,
  },
  emptyText: { fontSize: 16, fontWeight: '700', color: BLACK, marginBottom: 6, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  emptyHint: { fontSize: 13, color: GRAY, textAlign: 'center', lineHeight: 18, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
});
