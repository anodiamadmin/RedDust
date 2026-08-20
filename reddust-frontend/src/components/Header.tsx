// src/components/Header.tsx

import React from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppStore } from '../store/useAppStore';
import { BlurView } from 'expo-blur';
import { useNavigation } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { useAnimatedStyle, withTiming } from 'react-native-reanimated';

export default function Header() {
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const { activePersona, togglePersona } = useAppStore();
  const isSara = activePersona === 'sara';

  const handleOpenDrawer = () => {
    navigation.dispatch({ type: 'OPEN_DRAWER' });
  };

  const thumbStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: withTiming(isSara ? 16 : 0, { duration: 200 }) }],
  }));

  const thumbColor = isSara ? '#e42b10' : '#003153';
  const trackColor = isSara ? 'rgba(228, 43, 16, 0.2)' : 'rgba(0, 49, 83, 0.2)';

  return (
    <BlurView 
      intensity={80} // Matched to GlassTabBar's intensity
      tint="dark" 
      style={[styles.header, { paddingTop: insets.top + 12 }]}
    >
      <Pressable onPress={handleOpenDrawer} style={styles.menuButton}>
        <MaterialIcons name="menu" size={26} color="#e5e1e4" />
      </Pressable>

      <Text style={styles.title}>
        {isSara ? 'With Sara' : 'With Syan'}
      </Text>

      <Pressable 
        onPress={togglePersona}
        style={[styles.switchTrack, { backgroundColor: trackColor }]}
      >
        <Animated.View 
          style={[
            styles.switchThumb, 
            { backgroundColor: thumbColor }, 
            thumbStyle
          ]} 
        />
      </Pressable>
    </BlurView>
  );
}

const styles = StyleSheet.create({
  header: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 40,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.05)',
    backgroundColor: 'rgba(28, 27, 29, 0.95),', // Matched exact glass background color from GlassTabBar
  },
  menuButton: {
    padding: 8,
    borderRadius: 9999,
  },
  title: {
    color: '#ffffff',
    fontSize: 20,
    fontWeight: '300',
    letterSpacing: 0.5,
  },
  switchTrack: {
    width: 38,
    height: 16,
    borderRadius: 8,
    justifyContent: 'center',
    position: 'relative',
  },
  switchThumb: {
    width: 22,
    height: 22,
    borderRadius: 11,
    position: 'absolute',
    top: -3,
    left: 0,
  },
});