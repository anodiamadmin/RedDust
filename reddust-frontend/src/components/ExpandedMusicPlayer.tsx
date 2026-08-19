// src/components/ExpandedMusicPlayer.tsx

import React from 'react';
import { View, Text, Pressable, Image, Modal, StyleSheet } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppStore } from '../store/useAppStore';

export default function ExpandedMusicPlayer() {
  const { isExpandedPlayerOpen, toggleExpandedPlayer, currentTrack, activePersona } = useAppStore();

  return (
    <Modal
      visible={isExpandedPlayerOpen}
      animationType="slide"
      transparent={false} // Full screen opaque modal for a clean sheet look
    >
      <View style={styles.container}>
        
        {/* Top Header */}
        <View style={styles.topHeader}>
          <Pressable onPress={() => toggleExpandedPlayer(false)} style={styles.iconButton}>
            <MaterialIcons name="expand-more" size={32} color="#e5e1e4" />
          </Pressable>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>I handpicked this for you</Text>
          </View>
          <View style={{ width: 32 }} /> 
        </View>

        {/* Album Art */}
        <View style={styles.heroSection}>
          <Image 
            source={{ uri: 'https://via.placeholder.com/300' }} 
            style={styles.albumArt}
          />
        </View>

        {/* Track Title */}
        <View style={styles.titleSection}>
          <Text style={styles.trackTitle}>{currentTrack?.title || 'Midnight Dust'}</Text>
          <Text style={styles.trackArtist}>{currentTrack?.artist || 'RedDust Ambient'}</Text>
        </View>

        {/* AI Explainability Badge */}
        <View style={styles.aiCard}>
          <Text style={styles.aiText}>
            {activePersona === 'sara' ? 'Sara' : 'Syan'} selected this to help you decompress after your late shift.
          </Text>
        </View>

        {/* Main Playback Controls */}
        <View style={styles.controlsSection}>
          <Pressable>
            <MaterialIcons name="replay-10" size={36} color="#e5e1e4" />
          </Pressable>
          
          <Pressable style={styles.playPauseButton}>
            <MaterialIcons name="pause" size={48} color="#e42b10" />
          </Pressable>

          <Pressable>
            <MaterialIcons name="forward-10" size={36} color="#e5e1e4" />
          </Pressable>
        </View>

      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#131315', // Matches your Stitch surface background
    paddingTop: 48,
    paddingHorizontal: 24,
    justifyContent: 'space-between',
    paddingBottom: 48,
  },
  topHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  iconButton: {
    padding: 8,
  },
  badge: {
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 9999,
  },
  badgeText: {
    color: '#d1d1d6',
    fontSize: 12,
    fontWeight: '600',
  },
  heroSection: {
    alignItems: 'center',
    marginVertical: 20,
  },
  albumArt: {
    width: 280,
    height: 280,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  titleSection: {
    alignItems: 'center',
    marginBottom: 10,
  },
  trackTitle: {
    color: '#ffffff',
    fontSize: 24,
    fontWeight: '300',
    marginBottom: 4,
    textAlign: 'center',
  },
  trackArtist: {
    color: '#919096',
    fontSize: 16,
  },
  aiCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    padding: 16,
    borderRadius: 16,
    marginHorizontal: 16,
  },
  aiText: {
    color: '#e5e1e4',
    textAlign: 'center',
    fontSize: 14,
    lineHeight: 20,
  },
  controlsSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 32,
  },
  playPauseButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
});