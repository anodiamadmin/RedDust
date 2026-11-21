// src/app/(app)/_layout.tsx

import React from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { Drawer } from 'expo-router/drawer';
import { Redirect } from 'expo-router'; // <-- NEW IMPORT
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { MaterialIcons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuthStore } from '../../store/useAuthStore';

import MusicPlayer from '../../components/MusicPlayer';

function CustomDrawerContent(props: any) {
  const insets = useSafeAreaInsets();
  const signOut = useAuthStore((state) => state.signOut); 

  return (
    <View style={{ flex: 1, backgroundColor: '#131315', paddingTop: insets.top + 20 }}>
      <View style={{ flex: 1, paddingHorizontal: 24 }} />

      <View style={[styles.footer, { paddingBottom: insets.bottom + 24 }]}>
        <Pressable 
          onPress={() => { if(signOut) signOut(); }} 
          style={({ pressed }) => [styles.signOutButton, pressed && styles.signOutButtonPressed]}
        >
          <MaterialIcons name="logout" size={20} color="#e42b10" style={{ marginRight: 12 }} />
          <Text style={styles.signOutText}>Sign Out</Text>
        </Pressable>
      </View>
    </View>
  );
}

export default function AppDrawerLayout() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // 2. THE OFFICIAL EXPO ROUTER GUARD
  // If user logs out, instantly force the URL to the signin page
  if (!isAuthenticated) {
    return <Redirect href="/signin" />;
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <View style={{ flex: 1, backgroundColor: '#131315' }}>
        <Drawer
          drawerContent={(props) => <CustomDrawerContent {...props} />}
          screenOptions={{
            headerShown: false,
            drawerType: 'front', 
            drawerStyle: {
              backgroundColor: '#131315',
              width: '75%',
            },
            sceneStyle: {
              backgroundColor: '#131315',
            },
          }}
        >
          <Drawer.Screen name="(tabs)" options={{ drawerLabel: 'Home' }} />
        </Drawer>
        <MusicPlayer />
      </View>
    </GestureHandlerRootView>
  );
}

// ... styles remain the same

const styles = StyleSheet.create({
  footer: {
    paddingHorizontal: 24,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.05)',
  },
  signOutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e42b10',
    backgroundColor: 'transparent',
  },
  signOutButtonPressed: {
    backgroundColor: 'rgba(228, 43, 16, 0.1)',
    transform: [{ scale: 0.98 }],
  },
  signOutText: {
    color: '#e42b10',
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 1.2,
  },
});