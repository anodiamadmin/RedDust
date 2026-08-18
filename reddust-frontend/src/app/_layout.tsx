// src/app/_layout.tsx

import { Stack, useRouter, useSegments } from 'expo-router';
import { useEffect, useState } from 'react';
import * as SplashScreen from 'expo-splash-screen';
import { useAuthStore } from '../store/useAuthStore';

// Keep the splash screen visible while checking auth state
SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const segments = useSegments();
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);

  // Initialize and check hydration state
  useEffect(() => {
    const initializeAuth = async () => {
      // Short delay to allow secure storage / Zustand state to hydrate
      setTimeout(() => {
        setIsReady(true);
      }, 300);
    };

    initializeAuth();
  }, []);

  // Traffic Cop / Routing Guard Effect
  useEffect(() => {
    if (!isReady) return;

    const inAuthGroup = segments[0] === '(tabs)';

    if (!isAuthenticated && inAuthGroup) {
      // If not logged in and trying to access tabs, kick them back to sign-in
      router.replace('/signin');
    } else if (isAuthenticated && !inAuthGroup) {
      // If logged in and sitting on sign-in, warp them straight to tabs
      router.replace('/(tabs)');
    }

    // Hide the splash screen once routing decision has been enforced
    SplashScreen.hideAsync();
  }, [isAuthenticated, isReady, segments]);

  if (!isReady) {
    return null; // Prevent flashing while verifying auth state
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="signin" />
      <Stack.Screen name="(tabs)" />
    </Stack>
  );
}