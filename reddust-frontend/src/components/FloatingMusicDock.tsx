// src/components/FloatingMusicDock.tsx

import React from 'react';
import { View, Text, Pressable, Image, StyleSheet, Dimensions } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { useSharedValue, useAnimatedStyle, clamp } from 'react-native-reanimated';
import { useAppStore } from '../store/useAppStore';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

const DOCK_WIDTH = 350;
const DOCK_HEIGHT = 65;
const EDGE_PADDING = 16;

export default function FloatingMusicDock() {
  const { currentTrack, toggleExpandedPlayer } = useAppStore();

  const translationX = useSharedValue(0);
  // Default resting position near the bottom of the screen above tabs
  const defaultInitialY = SCREEN_HEIGHT - 170; 
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

      // Allow dragging all the way from the very top (below status bar) to the very bottom
      const minTranslateX = -(SCREEN_WIDTH / 2) + (DOCK_WIDTH / 2) + EDGE_PADDING;
      const maxTranslateX = (SCREEN_WIDTH / 2) - (DOCK_WIDTH / 2) - EDGE_PADDING;

      // Full screen vertical range bounded only by screen edges
      const minTranslateY = -defaultInitialY + 50; // Near top of screen
      const maxTranslateY = SCREEN_HEIGHT - defaultInitialY - DOCK_HEIGHT - EDGE_PADDING; // Near bottom of screen

      translationX.value = clamp(rawX, minTranslateX, maxTranslateX);
      translationY.value = clamp(rawY, minTranslateY, maxTranslateY);
    });

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: translationX.value },
      { translateY: translationY.value },
    ],
  }));

  if (!currentTrack) return null;

  return (
    <View style={styles.absoluteContainer} pointerEvents="box-none">
      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.container, animatedStyle]}>
          <Pressable 
            onPress={() => toggleExpandedPlayer(true)} 
            style={styles.dockBox}
          >
            {/* Album Art */}
            <View style={styles.albumArtContainer}>
              <Image 
                source={{ uri: 'https://via.placeholder.com/150' }} 
                style={styles.albumArt}
              />
            </View>

            {/* Track Info */}
            <View style={styles.trackInfo}>
              <Text style={styles.trackTitle} numberOfLines={1}>
                {currentTrack.title}
              </Text>
              <Text style={styles.trackArtist}>{currentTrack.artist}</Text>
              
              <View style={styles.progressBarBg}>
                <View style={styles.progressBarFill} />
              </View>
            </View>

            {/* Action Buttons */}
            <Pressable style={styles.iconButton} onPress={(e) => e.stopPropagation()}>
              <MaterialIcons name="favorite-border" size={18} color="#e5e1e4" />
            </Pressable>
            
            <Pressable style={styles.playButton} onPress={(e) => e.stopPropagation()}>
              <MaterialIcons name="pause" size={18} color="#131315" />
            </Pressable>
          </Pressable>
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  absoluteContainer: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 9999,
    elevation: 99,
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingBottom: 110,
    pointerEvents: 'box-none',
  },
  container: {
    alignItems: 'center',
  },
  dockBox: {
    width: DOCK_WIDTH,
    backgroundColor: '#201f21', // Stitch dark surface color
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 9999,
    padding: 8,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.5,
    shadowRadius: 15,
    elevation: 10,
  },
  albumArtContainer: {
    width: 42,
    height: 42,
    borderRadius: 21,
    overflow: 'hidden',
    marginRight: 10,
  },
  albumArt: {
    width: '100%',
    height: '100%',
  },
  trackInfo: {
    flex: 1,
    overflow: 'hidden',
    marginRight: 6,
  },
  trackTitle: {
    color: '#ffffff',
    fontWeight: '600',
    fontSize: 12,
  },
  trackArtist: {
    color: '#c7c5cc',
    fontSize: 10,
  },
  progressBarBg: {
    width: '100%',
    backgroundColor: '#353437',
    height: 3,
    borderRadius: 2,
    marginTop: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    backgroundColor: '#e42b10',
    width: '33%',
    height: '100%',
  },
  iconButton: {
    padding: 6,
  },
  playButton: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 4,
    marginRight: 4,
  },
});