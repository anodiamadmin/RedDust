// src/components/Header.tsx

import React from 'react';
import { View, Text, Pressable, Switch, StyleSheet } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppStore } from '../store/useAppStore';
import { BlurView } from 'expo-blur';
import { useNavigation } from 'expo-router';

export default function Header() {
  const navigation = useNavigation();
  const { activePersona, togglePersona } = useAppStore();
  const isSara = activePersona === 'sara';

  const handleOpenDrawer = () => {
    // Native Expo Router drawer trigger
    const navAny = navigation as any;
    if (navAny.openDrawer) {
      navAny.openDrawer();
    } else if (navAny.getParent?.()) {
      navAny.getParent().openDrawer?.();
    }
  };

  return (
    <BlurView intensity={30} tint="dark" style={styles.header}>
      {/* Hamburger Menu - Fully tappable */}
      <Pressable onPress={handleOpenDrawer} style={styles.menuButton}>
        <MaterialIcons name="menu" size={26} color="#e5e1e4" />
      </Pressable>

      {/* Dynamic Title */}
      <Text style={styles.title}>
        {isSara ? 'With Sara' : 'With Syan'}
      </Text>

      {/* Persona Toggle */}
      <View style={styles.toggleContainer}>
        <Switch 
          value={isSara}
          onValueChange={togglePersona}
          trackColor={{ false: '#003153', true: '#e42b10' }}
          thumbColor="#ffffff"
        />
      </View>
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
    paddingTop: 50,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.05)',
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
  toggleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
});