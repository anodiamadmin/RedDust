// src/app/_layout.tsx

import { Stack } from 'expo-router';
import { useEffect, useState } from 'react';
import * as SplashScreen from 'expo-splash-screen';
import { useAuthStore } from '../store/useAuthStore';
import { useFonts } from 'expo-font';
import { GoogleSignin } from '@react-native-google-signin/google-signin';

// 1. CONFIGURE GOOGLE AT THE ABSOLUTE ROOT
// Now it works flawlessly even if the sign-in screen never mounts!
GoogleSignin.configure({
  webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID, 
  iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID, 
  offlineAccess: true,
});

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [isReady, setIsReady] = useState(false);

  const [fontsLoaded] = useFonts({
    'GoogleSans-Medium': require('../../assets/fonts/GoogleSans-Medium.ttf'),
  });

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

  useEffect(() => {
    if (isReady && fontsLoaded) {
      SplashScreen.hideAsync();
    }
  }, [isReady, fontsLoaded]); 

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