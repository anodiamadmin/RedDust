// src/app/(app)/(tabs)/index.tsx

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

export default function SoulmateScreen() {
  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <Text style={styles.text}>Soulmate Chat (Sara/Syan)</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0c', 
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  text: {
    color: '#8E8E93',
    fontSize: 16,
    fontFamily: 'GoogleSans-Medium', 
  },
});