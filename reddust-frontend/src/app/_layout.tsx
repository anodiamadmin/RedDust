// src/app/_layout.tsx

import { Stack, useRouter, usePathname } from 'expo-router';
import { useEffect, useState } from 'react';
import * as SplashScreen from 'expo-splash-screen';
import { useAuthStore } from '../store/useAuthStore';
import { useFonts } from 'expo-font';

// Keep splash screen visible while loading resources
SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const pathname = usePathname();
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);

  // Load the official Google Sans font from your assets folder
  const [fontsLoaded] = useFonts({
    'GoogleSans-Medium': require('../../assets/fonts/GoogleSans-Medium.ttf'),
  });

  // Wait for Zustand to finish loading persisted storage from device disk
  useEffect(() => {
    const checkHydration = () => {
      if (useAuthStore.persist.hasHydrated()) {
        setIsReady(true);
      } else {
        const unsubHydrate = useAuthStore.persist.onFinishHydration(() => {
          setIsReady(true);
        });
        return unsubHydrate;
      }
    };
    checkHydration();
  }, []);

  // Traffic Cop / Routing Guard Effect
  useEffect(() => {
    // Wait until both storage hydration AND font loading are completely done
    if (!isReady || !fontsLoaded) return; 

    const timer = setTimeout(() => {
      const isSignInScreen = pathname === '/signin';

      if (!isAuthenticated && !isSignInScreen) {
        router.replace('/signin');
      } else if (isAuthenticated && isSignInScreen) {
        router.replace('/');
      }

      SplashScreen.hideAsync();
    }, 50);

    return () => clearTimeout(timer);
  }, [isAuthenticated, isReady, fontsLoaded, pathname]); 

  if (!isReady || !fontsLoaded) {
    return null; 
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="signin" />
      <Stack.Screen name="(app)" />
    </Stack>
  );
}