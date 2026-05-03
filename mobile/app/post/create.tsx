import { useState } from 'react';
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
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { trayApi, PostCategory } from '@/api/tray';

const PRIMARY = '#2B3A2E';
const BG = '#FAFAF7';
const CARD = '#FFFFFF';
const BLACK = '#1A1A1A';
const GRAY = '#6E7E70';
const BORDER = '#D4DAD5';

const CATEGORIES: Array<{ key: PostCategory; label: string; icon: string; color: string }> = [
  { key: 'recipe',     label: 'Рецепт',      icon: 'restaurant-outline',  color: '#C9A14B' },
  { key: 'lifehack',   label: 'Лайфхак',     icon: 'flash-outline',       color: '#4A5C4D' },
  { key: 'progress',   label: 'Прогресс',    icon: 'trending-up-outline', color: '#5A7A5C' },
  { key: 'idea',       label: 'Идея',        icon: 'bulb-outline',        color: '#C8553D' },
  { key: 'discussion', label: 'Обсуждение',  icon: 'chatbubbles-outline', color: '#6E7E70' },
];

const MAX_IMAGE_WIDTH = 1200;
const JPEG_QUALITY = 0.85;

// Compress an image file via canvas before encoding to base64.
// Keeps payloads under ~500KB.
function compressImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new window.Image();
      img.onload = () => {
        const ratio = Math.min(1, MAX_IMAGE_WIDTH / img.width);
        const w = Math.round(img.width * ratio);
        const h = Math.round(img.height * ratio);
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Canvas error'));
          return;
        }
        ctx.drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL('image/jpeg', JPEG_QUALITY));
      };
      img.onerror = reject;
      img.src = reader.result as string;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function CreatePostScreen() {
  const [category, setCategory] = useState<PostCategory>('recipe');
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [image, setImage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [imageProcessing, setImageProcessing] = useState(false);

  const pickImage = () => {
    if (typeof document === 'undefined') return;
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async (e: any) => {
      const file = e.target.files?.[0] as File | undefined;
      if (!file) return;
      setImageProcessing(true);
      try {
        const dataUrl = await compressImage(file);
        setImage(dataUrl);
      } catch {
        // fallback: use raw file as data URL
        const reader = new FileReader();
        reader.onload = () => setImage(reader.result as string);
        reader.readAsDataURL(file);
      } finally {
        setImageProcessing(false);
      }
    };
    input.click();
  };

  const removeImage = () => setImage(null);

  const handleSubmit = async () => {
    if (!title.trim() || submitting) return;
    setSubmitting(true);
    try {
      const post = await trayApi.create({
        category,
        title: title.trim(),
        text: text.trim(),
        image_url: image,
      });
      router.replace(`/post/${post.id}`);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Не удалось опубликовать';
      if (typeof window !== 'undefined') window.alert(msg);
      setSubmitting(false);
    }
  };

  const canSubmit = title.trim().length > 0 && !submitting;

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={s.headerBar}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn} activeOpacity={0.7}>
            <Ionicons name="close" size={24} color={BLACK} />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Новый пост</Text>
          <TouchableOpacity
            style={[s.publishBtn, !canSubmit && s.publishBtnDisabled]}
            onPress={handleSubmit}
            disabled={!canSubmit}
            activeOpacity={0.85}
          >
            {submitting ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.publishBtnText}>Опубликовать</Text>}
          </TouchableOpacity>
        </View>

        <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
          <Text style={s.label}>Категория</Text>
          <View style={s.catGrid}>
            {CATEGORIES.map((c) => {
              const active = category === c.key;
              return (
                <TouchableOpacity
                  key={c.key}
                  style={[s.catBtn, active && s.catBtnActive]}
                  onPress={() => setCategory(c.key)}
                  activeOpacity={0.8}
                >
                  <Ionicons name={c.icon as any} size={12} color={active ? '#FFF' : GRAY} />
                  <Text style={[s.catBtnText, active && s.catBtnTextActive]}>
                    {c.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <Text style={s.label}>Картинка</Text>
          {image ? (
            <View style={s.imagePreview}>
              <Image source={{ uri: image }} style={s.imagePreviewImg} resizeMode="cover" />
              <TouchableOpacity style={s.imageRemoveBtn} onPress={removeImage} activeOpacity={0.85}>
                <Ionicons name="close" size={16} color="#FFF" />
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity style={s.imagePickerBtn} onPress={pickImage} activeOpacity={0.85} disabled={imageProcessing}>
              {imageProcessing ? (
                <ActivityIndicator color={PRIMARY} />
              ) : (
                <>
                  <Ionicons name="image-outline" size={28} color={GRAY} />
                  <Text style={s.imagePickerText}>Выбрать из галереи</Text>
                  <Text style={s.imagePickerHint}>Опционально, но с картинкой красивее</Text>
                </>
              )}
            </TouchableOpacity>
          )}

          <Text style={s.label}>Заголовок</Text>
          <TextInput
            style={s.titleInput}
            placeholder="Например: «Курица за 30 минут»"
            placeholderTextColor={GRAY}
            value={title}
            onChangeText={setTitle}
            maxLength={200}
          />

          <Text style={s.label}>Текст</Text>
          <TextInput
            style={s.textInput}
            placeholder="Расскажи поподробнее..."
            placeholderTextColor={GRAY}
            value={text}
            onChangeText={setText}
            multiline
            maxLength={5000}
          />

          <View style={{ height: 40 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  headerBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: CARD,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
    gap: 8,
  },
  backBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  headerTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '800',
    color: BLACK,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  publishBtn: {
    backgroundColor: PRIMARY,
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 8,
    minWidth: 110,
    alignItems: 'center',
  },
  publishBtnDisabled: { opacity: 0.4 },
  publishBtnText: { color: '#FFF', fontSize: 13, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  content: { padding: 16, gap: 8 },
  label: {
    fontSize: 12,
    fontWeight: '800',
    color: GRAY,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: 8,
    marginBottom: 4,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  catGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  catBtn: {
    backgroundColor: CARD,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: BORDER,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  catBtnActive: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  catBtnText: { color: GRAY, fontSize: 13, fontWeight: '700', fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  catBtnTextActive: { color: '#FFF' },
  imagePickerBtn: {
    backgroundColor: CARD,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: BORDER,
    borderStyle: 'dashed',
    paddingVertical: 24,
    alignItems: 'center',
    gap: 6,
  },
  imagePickerText: { fontSize: 14, fontWeight: '700', color: BLACK, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  imagePickerHint: { fontSize: 11, color: GRAY, fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" },
  imagePreview: { borderRadius: 14, overflow: 'hidden', position: 'relative' },
  imagePreviewImg: { width: '100%', height: 200, backgroundColor: '#F0EEE7' },
  imageRemoveBtn: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  titleInput: {
    backgroundColor: CARD,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: BORDER,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    fontWeight: '700',
    color: BLACK,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  textInput: {
    backgroundColor: CARD,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: BORDER,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    color: BLACK,
    minHeight: 140,
    textAlignVertical: 'top',
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
});
