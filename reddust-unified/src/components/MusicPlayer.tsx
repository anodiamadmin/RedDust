// src/components/MusicPlayer.tsx

import React from 'react';
import { View, Text, Pressable, Image, Modal, StyleSheet, Dimensions } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { useSharedValue, useAnimatedStyle, clamp } from 'react-native-reanimated';
import { useAppStore } from '../store/useAppStore';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

// --- CONSTANTS ---
const DOCK_WIDTH = 350;
const DOCK_HEIGHT = 65;
const EDGE_PADDING = 16;
const DEFAULT_INITIAL_Y = SCREEN_HEIGHT - 170;

export default function MusicPlayer() {
  const { currentTrack, activePersona, isExpandedPlayerOpen, toggleExpandedPlayer } = useAppStore();

  // --- GESTURE STATE (Floating Dock) ---
  const translationX = useSharedValue(0);
  const translationY = useSharedValue(0);
  const prevTranslationX = useSharedValue(0);
  const prevTranslationY = useSharedValue(0);

  const panGesture = Gesture.Pan()
    .onStart(() => {
      prevTranslationX.value = translationX.value;
      prevTranslationY.value = translationY.value;
    })
    .onUpdate((event) => {
      const rawX = prevTranslationX.value + event.translationX;
      const rawY = prevTranslationY.value + event.translationY;

      const minTranslateX = -(SCREEN_WIDTH / 2) + (DOCK_WIDTH / 2) + EDGE_PADDING;
      const maxTranslateX = (SCREEN_WIDTH / 2) - (DOCK_WIDTH / 2) - EDGE_PADDING;

      const minTranslateY = -DEFAULT_INITIAL_Y + 50; 
      const maxTranslateY = SCREEN_HEIGHT - DEFAULT_INITIAL_Y - DOCK_HEIGHT - EDGE_PADDING;

      translationX.value = clamp(rawX, minTranslateX, maxTranslateX);
      translationY.value = clamp(rawY, minTranslateY, maxTranslateY);
    });

  const animatedFloatingStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: translationX.value },
      { translateY: translationY.value },
    ],
    // Hide floating dock completely if expanded player is open
    opacity: isExpandedPlayerOpen ? 0 : 1, 
  }));

  // 1. GATEKEEPER: If no track is playing, the entire component renders nothing.
  if (!currentTrack) return null;

  return (
    <>
      {/* --- STATE 1: FLOATING DOCK --- */}
      <View style={styles.absoluteContainer} pointerEvents={isExpandedPlayerOpen ? 'none' : 'box-none'}>
        <GestureDetector gesture={panGesture}>
          <Animated.View style={[styles.dockContainer, animatedFloatingStyle]}>
            <Pressable onPress={() => toggleExpandedPlayer(true)} style={styles.dockBox}>
              
              <View style={styles.dockAlbumArtContainer}>
                {/* Fallback image if currentTrack doesn't have artwork yet */}
                <Image source={{ uri: 'https://via.placeholder.com/150' }} style={styles.fullImage} />
              </View>

              <View style={styles.dockTrackInfo}>
                <Text style={styles.dockTrackTitle} numberOfLines={1}>{currentTrack.title}</Text>
                <Text style={styles.dockTrackArtist}>{currentTrack.artist}</Text>
                
                <View style={styles.progressBarBg}>
                  <View style={styles.progressBarFill} />
                </View>
              </View>

              <Pressable style={styles.iconButton} onPress={(e) => e.stopPropagation()}>
                <MaterialIcons name="favorite-border" size={18} color="#e5e1e4" />
              </Pressable>
              
              <Pressable style={styles.dockPlayButton} onPress={(e) => e.stopPropagation()}>
                <MaterialIcons name="pause" size={18} color="#131315" />
              </Pressable>
            </Pressable>
          </Animated.View>
        </GestureDetector>
      </View>

      {/* --- STATE 2: EXPANDED MODAL --- */}
      <Modal visible={isExpandedPlayerOpen} animationType="slide" transparent={false}>
        <View style={styles.expandedContainer}>
          
          <View style={styles.expandedTopHeader}>
            <Pressable onPress={() => toggleExpandedPlayer(false)} style={styles.iconButton}>
              <MaterialIcons name="expand-more" size={32} color="#e5e1e4" />
            </Pressable>
            <View style={styles.expandedBadge}>
              <Text style={styles.expandedBadgeText}>I handpicked this for you</Text>
            </View>
            <View style={{ width: 32 }} /> 
          </View>

          <View style={styles.expandedHeroSection}>
            <Image source={{ uri: 'https://via.placeholder.com/300' }} style={styles.expandedAlbumArt} />
          </View>

          <View style={styles.expandedTitleSection}>
            <Text style={styles.expandedTrackTitle}>{currentTrack.title}</Text>
            <Text style={styles.expandedTrackArtist}>{currentTrack.artist}</Text>
          </View>

          <View style={styles.aiCard}>
            <Text style={styles.aiText}>
              {activePersona === 'sara' ? 'Sara' : 'Syan'} selected this to help you decompress after your late shift.
            </Text>
          </View>

          <View style={styles.expandedControlsSection}>
            <Pressable>
              <MaterialIcons name="replay-10" size={36} color="#e5e1e4" />
            </Pressable>
            
            <Pressable style={styles.expandedPlayPauseButton}>
              <MaterialIcons name="pause" size={48} color="#e42b10" />
            </Pressable>

            <Pressable>
              <MaterialIcons name="forward-10" size={36} color="#e5e1e4" />
            </Pressable>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  // --- SHARED / UTILS ---
  fullImage: { width: '100%', height: '100%' },
  iconButton: { padding: 6 },
  
  // --- FLOATING DOCK STYLES ---
  absoluteContainer: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 9999,
    elevation: 99,
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingBottom: 110,
  },
  dockContainer: { alignItems: 'center' },
  dockBox: {
    width: DOCK_WIDTH,
    backgroundColor: '#201f21', 
    borderWidth: 1, borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 9999,
    padding: 8,
    flexDirection: 'row', alignItems: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 10 }, shadowOpacity: 0.5, shadowRadius: 15, elevation: 10,
  },
  dockAlbumArtContainer: {
    width: 42, height: 42,
    borderRadius: 21, overflow: 'hidden',
    marginRight: 10,
  },
  dockTrackInfo: { flex: 1, overflow: 'hidden', marginRight: 6 },
  dockTrackTitle: { color: '#ffffff', fontWeight: '600', fontSize: 12 },
  dockTrackArtist: { color: '#c7c5cc', fontSize: 10 },
  progressBarBg: { width: '100%', backgroundColor: '#353437', height: 3, borderRadius: 2, marginTop: 4, overflow: 'hidden' },
  progressBarFill: { backgroundColor: '#e42b10', width: '33%', height: '100%' },
  dockPlayButton: {
    width: 34, height: 34, borderRadius: 17,
    backgroundColor: '#ffffff', alignItems: 'center', justifyContent: 'center',
    marginLeft: 4, marginRight: 4,
  },

  // --- EXPANDED MODAL STYLES ---
  expandedContainer: {
    flex: 1, backgroundColor: '#131315',
    paddingTop: 48, paddingHorizontal: 24, paddingBottom: 48,
    justifyContent: 'space-between',
  },
  expandedTopHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  expandedBadge: { backgroundColor: 'rgba(255, 255, 255, 0.1)', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 9999 },
  expandedBadgeText: { color: '#d1d1d6', fontSize: 12, fontWeight: '600' },
  expandedHeroSection: { alignItems: 'center', marginVertical: 20 },
  expandedAlbumArt: { width: 280, height: 280, borderRadius: 24, borderWidth: 1, borderColor: 'rgba(255, 255, 255, 0.1)' },
  expandedTitleSection: { alignItems: 'center', marginBottom: 10 },
  expandedTrackTitle: { color: '#ffffff', fontSize: 24, fontWeight: '300', marginBottom: 4, textAlign: 'center' },
  expandedTrackArtist: { color: '#919096', fontSize: 16 },
  aiCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)', borderWidth: 1, borderColor: 'rgba(255, 255, 255, 0.1)',
    padding: 16, borderRadius: 16, marginHorizontal: 16,
  },
  aiText: { color: '#e5e1e4', textAlign: 'center', fontSize: 14, lineHeight: 20 },
  expandedControlsSection: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 32 },
  expandedPlayPauseButton: {
    width: 80, height: 80, borderRadius: 40,
    backgroundColor: '#ffffff', alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 8,
  },
});