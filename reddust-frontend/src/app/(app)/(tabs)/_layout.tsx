// src/app/(app)/(tabs)/_layout.tsx

import React from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { Tabs } from 'expo-router';
import { MaterialIcons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import Header from '../../../components/Header';

function GlassTabBar({ state, descriptors, navigation }: any) {
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.tabBarContainer, { paddingBottom: insets.bottom ? insets.bottom + 10 : 20 }]}>
      <BlurView intensity={80} tint="dark" style={styles.blurView}>
        {state.routes.map((route: any, index: number) => {
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

          let iconName: keyof typeof MaterialIcons.glyphMap = 'mic';
          let label = 'Soulmate';

          if (route.name === 'index') {
            label = 'Soulmate';
            iconName = 'mic';
          } else if (route.name === 'soul-space') {
            label = 'Soul Space';
            iconName = 'favorite-border';
          }

          const brandRed = '#e42b10';
          const mutedGray = 'rgba(199, 197, 204, 0.6)';

          return (
            <Pressable
              key={route.key}
              onPress={onPress}
              style={[styles.tabItem, isFocused && styles.tabItemActive]}
            >
              <MaterialIcons
                name={iconName}
                size={22}
                color={isFocused ? brandRed : mutedGray}
                style={{ marginBottom: 2 }}
              />
              <Text style={{ fontSize: 11, fontWeight: '600', color: isFocused ? brandRed : mutedGray }}>
                {label}
              </Text>
            </Pressable>
          );
        })}
      </BlurView>
    </View>
  );
}

export default function TabLayout() {
  return (
    <View style={{ flex: 1, backgroundColor: '#0a0a0c' }}>
      <Header />
      <Tabs
        tabBar={(props) => <GlassTabBar {...props} />}
        screenOptions={{ headerShown: false }}
      >
        <Tabs.Screen name="index" />
        <Tabs.Screen name="soul-space" />
      </Tabs>
    </View>
  );
}

const styles = StyleSheet.create({
  tabBarContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 10,
  },
  blurView: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingTop: 12,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.05)',
    backgroundColor: 'rgba(28, 27, 29, 0.95)',
    overflow: 'hidden',
  },
  tabItem: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 6,
    paddingHorizontal: 20,
    borderRadius: 9999,
    minWidth: 90,
  },
  tabItemActive: {
    backgroundColor: 'rgba(228, 43, 16, 0.15)',
  },
});