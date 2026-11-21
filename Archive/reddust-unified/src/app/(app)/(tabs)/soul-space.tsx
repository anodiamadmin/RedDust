// src/app/(app)/(tabs)/soul-space.tsx

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

export default function SoulSpaceScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>Soul Space Ecosystem</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0c', 
    justifyContent: 'center',
    alignItems: 'center',
  },
  text: {
    color: '#8E8E93',
    fontSize: 16,
    fontFamily: 'GoogleSans-Medium',
  },
});