import { useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryProvider } from '../src/providers/QueryProvider';
import { useAuthStore } from '../src/store/authStore';
import { usePlanStore } from '../src/store/planStore';

function AuthGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isHydrated, onboardingCompleted, hydrate } = useAuthStore();
  const hydratePlan = usePlanStore((s) => s.hydratePlan);
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    hydrate();
    hydratePlan();
  }, []);

  useEffect(() => {
    if (!isHydrated) return;

    const inOnboarding = segments[0] === 'onboarding';

    if (!isAuthenticated) {
      // Not logged in — go to onboarding to create account
      if (!inOnboarding) router.replace('/onboarding' as any);
    } else {
      // Logged in — check if onboarding was completed
      if (!onboardingCompleted && !inOnboarding) {
        router.replace('/onboarding/step1');
      } else if (onboardingCompleted && inOnboarding) {
        router.replace('/(tabs)');
      }
    }
  }, [isAuthenticated, isHydrated, onboardingCompleted, segments]);

  // Show nothing while hydrating tokens from storage
  if (!isHydrated) return null;

  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <QueryProvider>
      <StatusBar style="dark" backgroundColor="#FAFAF7" />
      <AuthGate>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="onboarding" />
          <Stack.Screen name="post/[id]" />
          <Stack.Screen name="post/create" options={{ presentation: 'modal' }} />
        </Stack>
      </AuthGate>
    </QueryProvider>
  );
}
