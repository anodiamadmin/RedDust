// src/app/(tabs)/_layout.tsx

import React from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { Tabs } from 'expo-router';
import { MaterialIcons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

// 1. We create a custom component that replaces the default bottom bar
function GlassTabBar({ state, descriptors, navigation }: any) {
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.tabBarContainer, { paddingBottom: insets.bottom ? insets.bottom + 10 : 24 }]}>
      <BlurView intensity={80} tint="dark" style={styles.blurView}>
        {state.routes.map((route: any, index: number) => {
          const { options } = descriptors[route.key];
          const isFocused = state.index === index;

          const onPress = () => {
            const event = navigation.emit({
              type: 'tabPress',
              target: route.key,
              canPreventDefault: true,
            });

            if (!isFocused && !event.defaultPrevented) {
              navigation.navigate(route.name);
            }
          };

          // Determine Icon and Label based on route name
          let iconName: any = 'mic';
          let label = 'Soulmate';

          if (route.name === 'soul-space') {
            // Dynamic outlined/filled heart based on focus state
            iconName = isFocused ? 'favorite-border' : 'favorite-border';
            label = 'Soul Space';
          }

          // Colors mapped exactly from your Stitch Tailwind config
          const brandRed = '#e42b10';
          const mutedGray = 'rgba(199, 197, 204, 0.6)'; // on-surface-variant at 60%

          return (
            <Pressable
              key={route.key}
              onPress={onPress}
              style={[
                styles.tabItem,
                isFocused && styles.tabItemActive // Adds the red pill background if active
              ]}
            >
              <MaterialIcons
                name={iconName}
                size={24}
                color={isFocused ? brandRed : mutedGray}
                style={{ marginBottom: 4 }}
              />
              <Text
                style={{
                  fontSize: 12,
                  fontWeight: '600',
                  color: isFocused ? brandRed : mutedGray,
                }}
              >
                {label}
              </Text>
            </Pressable>
          );
        })}
      </BlurView>
    </View>
  );
}

// 2. We pass our custom GlassTabBar into the Expo Router Tabs
export default function TabLayout() {
  return (
    <Tabs
      tabBar={(props) => <GlassTabBar {...props} />}
      screenOptions={{ headerShown: false }}
    >
      <Tabs.Screen name="index" />
      <Tabs.Screen name="soul-space" />
    </Tabs>
  );
}

// 3. Exact mappings of the Stitch CSS
const styles = StyleSheet.create({
  tabBarContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    // The shadow from your Tailwind code: shadow-[0_-10px_40px_rgba(197,197,216,0.05)]
    shadowColor: '#c5c5d8',
    shadowOffset: { width: 0, height: -10 },
    shadowOpacity: 0.05,
    shadowRadius: 40,
    elevation: 10, 
  },
  blurView: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingTop: 16,
    borderTopLeftRadius: 24, // rounded-t-xl
    borderTopRightRadius: 24,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.05)', // border-white/5
    overflow: 'hidden',
    backgroundColor: 'rgba(28, 27, 29, 0.4)', // bg-surface-container-low with opacity
  },
  tabItem: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    paddingHorizontal: 24,
    borderRadius: 9999, // rounded-full
    minWidth: 100,
  },
  tabItemActive: {
    backgroundColor: 'rgba(228, 43, 16, 0.1)', // bg-brand-red/10
  }
});