// src/components/GoogleSignInButton.tsx

import React from 'react';
import { View, Text, StyleSheet, Pressable, Image } from 'react-native';
import { useAuthStore } from '../store/useAuthStore';
import { GoogleSignin, statusCodes } from '@react-native-google-signin/google-signin';
import { router } from 'expo-router'; // 1. IMPORT ROUTER HERE

export default function GoogleSignInButton() {
  const signInStore = useAuthStore((state) => state.signIn);

  const handleGoogleSignIn = async () => {
    try {
      await GoogleSignin.hasPlayServices();
      const response = await GoogleSignin.signIn();
      
      if (response.type === 'success') {
        console.log("SUCCESS! User Info: ", response.data);
        
        // 2. Update global state
        signInStore(response.data);
        
        // 3. TELL EXPO ROUTER TO GO TO THE MAIN APP (ADD THIS BACK)
        router.replace('/'); 
        
      } else if (response.type === 'cancelled') {
        console.log('User cancelled the login flow by pressing back.');
      }
      
    } catch (error: any) {
      if (error.code === statusCodes.IN_PROGRESS) {
        console.log('Sign in is already in progress');
      } else if (error.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
        console.log('Play services not available or outdated');
      } else {
        console.log('Some other error happened:', error);
      }
    }
  };

  return (
    <Pressable 
      style={({ pressed }) => [
        styles.googleButton,
        pressed && styles.googleButtonPressed
      ]} 
      onPress={handleGoogleSignIn}
    >
      <View style={styles.buttonContent}>
        <Image 
          source={require('../../assets/images/google-logo.png')} 
          style={styles.googleIconImage} 
        />
        <Text style={styles.buttonText}>Sign in with Google</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  googleButton: {
    width: 312, 
    height: 54,
    backgroundColor: '#131314', // Google Dark Theme standard background
    borderWidth: 1,
    borderColor: '#747775', // Google Dark Theme border color
    borderRadius: 9999, // Pill shape
    justifyContent: 'center',
    alignItems: 'center', // Centers the content wrapper
  },
  googleButtonPressed: {
    backgroundColor: 'rgba(255, 255, 255, 0.08)', 
    transform: [{ scale: 0.98 }],
  },
  buttonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center', // Centers the text perfectly within the button
    width: '100%',
    height: '100%',
  },
  googleIconImage: {
    position: 'absolute', // Floats the icon so it doesn't push the text
    left: 8, // Google's mandated 8px padding from the left edge
    width: 38,
    height: 38,
    resizeMode: 'contain',
  },
  buttonText: {
    color: '#E3E3E3', 
    fontSize: 16,
    fontFamily: 'GoogleSans-Medium', 
    letterSpacing: 0.25,
  }
});