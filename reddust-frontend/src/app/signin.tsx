// src/app/signin.tsx

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Pressable, Image } from 'react-native';
import Animated, { 
  useSharedValue, 
  useAnimatedStyle, 
  withTiming, 
  withDelay, 
  Easing 
} from 'react-native-reanimated';
import { useAuthStore } from '../store/useAuthStore';
import { GoogleSignin, statusCodes } from '@react-native-google-signin/google-signin';
import { router } from 'expo-router';

// We use an array of colors for the Google "G" to make it pop
const GOOGLE_COLORS = ['#4285F4', '#34A853', '#FBBC05', '#EA4335'];

// --- GOOGLE CONFIGURATION ---
// Safely pulling the Web Client ID from your .env file

GoogleSignin.configure({
  webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID, 
  offlineAccess: true,
});

export default function SigninScreen() {
  const signInStore = useAuthStore((state) => state.signIn);

  // --- Real Google Sign-In Logic ---
  const handleGoogleSignIn = async () => {
    try {
      await GoogleSignin.hasPlayServices();
      const userInfo = await GoogleSignin.signIn();
      console.log("SUCCESS! User Info: ", userInfo);
      
      // 1. Pass the user info to Zustand store
      signInStore(userInfo);
      
      // 2. Explicitly navigate to the tabs screen to prevent bouncing back
      router.replace('/(tabs)');
    } catch (error: any) {
      if (error.code === statusCodes.SIGN_IN_CANCELLED) {
        console.log('User cancelled the login flow');
      } else if (error.code === statusCodes.IN_PROGRESS) {
        console.log('Sign in is already in progress');
      } else if (error.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
        console.log('Play services not available or outdated');
      } else {
        console.log('Some other error happened:', error);
      }
    }
  };

  // --- Animation Shared Values ---
  // Background Image (15s Journey)
  const bgScale = useSharedValue(1);
  const bgTranslateY = useSharedValue(0);
  
  // Brand & Typography
  const nameOpacity = useSharedValue(0);
  const brandTranslateY = useSharedValue(32); // Starts 32px down
  
  // Tagline Typing Effect (Handled via React State for the typing illusion)
  const fullTagline = "Listen to the music that listens to your soul";
  const [displayedTagline, setDisplayedTagline] = useState('');
  const [showCursor, setShowCursor] = useState(false);

  // Login Button
  const buttonOpacity = useSharedValue(0);
  const buttonTranslateY = useSharedValue(50); // Starts 50px down

  useEffect(() => {
    // 1. Start the 15-second slow background zoom/pan instantly
    bgScale.value = withTiming(1.15, { duration: 15000, easing: Easing.out(Easing.quad) });
    bgTranslateY.value = withTiming(-20, { duration: 15000, easing: Easing.out(Easing.quad) });

    // 2. Fade in "RedDust" after 1 second
    nameOpacity.value = withDelay(1000, withTiming(1, { duration: 1000 }));

    // 3. Move the whole brand container up after 2.5 seconds
    brandTranslateY.value = withDelay(2500, withTiming(-32, { duration: 1000, easing: Easing.out(Easing.exp) }));

    // 4. Start the Tagline typing animation at 3.3 seconds (2.5s + 0.8s)
    const typingTimeout = setTimeout(() => {
      setShowCursor(true);
      let i = 0;
      const interval = setInterval(() => {
        setDisplayedTagline(fullTagline.slice(0, i + 1));
        i++;
        if (i >= fullTagline.length) {
          clearInterval(interval);
          setShowCursor(false);
        }
      }, 40); // Speed of typing
    }, 3300);

    // 5. Slide and fade in the Google button at 4 seconds
    buttonOpacity.value = withDelay(4000, withTiming(1, { duration: 800 }));
    buttonTranslateY.value = withDelay(4000, withTiming(0, { duration: 800, easing: Easing.out(Easing.back(1.5)) }));

    return () => clearTimeout(typingTimeout);
  }, []);

  // --- Animated Styles ---
  const animatedBgStyle = useAnimatedStyle(() => ({
    transform: [{ scale: bgScale.value }, { translateY: bgTranslateY.value }],
  }));

  const animatedNameStyle = useAnimatedStyle(() => ({
    opacity: nameOpacity.value,
  }));

  const animatedBrandContainerStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: brandTranslateY.value }],
  }));

  const animatedButtonStyle = useAnimatedStyle(() => ({
    opacity: buttonOpacity.value,
    transform: [{ translateY: buttonTranslateY.value }],
  }));

  return (
    <View style={styles.container}>
      {/* Background Image with Journey Animation */}
      <Animated.Image 
        source={require('../../assets/images/splash-screen.jpg')} 
        style={[styles.backgroundImage, animatedBgStyle]}
        resizeMode="cover"
      />
      
      {/* Dark Gradient Overlay equivalent */}
      <View style={styles.overlay} />

      <View style={styles.contentContainer}>
        
        {/* Brand Container */}
        <Animated.View style={[styles.brandContainer, animatedBrandContainerStyle]}>
          
          {/* Logo Placeholder */}
          <View style={styles.logoContainer}>
            <View style={styles.logoGlow} />
            <Image source={require('../../assets/images/logo.png')} style={styles.logo} />
          </View>

          {/* App Name */}
          <Animated.Text style={[styles.appName, animatedNameStyle]}>
            RedDust
          </Animated.Text>

          {/* Tagline */}
          <View style={styles.taglineWrapper}>
            <Text style={styles.tagline}>
              {displayedTagline}
              {showCursor ? <Text style={styles.cursor}>|</Text> : null}
            </Text>
          </View>
        </Animated.View>

        {/* Login Action */}
        <Animated.View style={[styles.loginContainer, animatedButtonStyle]}>
          <Pressable 
            style={({ pressed }) => [
              styles.googleButton,
              pressed && styles.googleButtonPressed
            ]} 
            onPress={handleGoogleSignIn} // Triggers Native Google Auth & Navigation
          >
            <View style={styles.buttonContent}>
              <Text style={styles.googleIcon}>G</Text>
              <Text style={styles.buttonText}>Sign in with Google</Text>
            </View>
          </Pressable>
        </Animated.View>

      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#131315',
  },
  backgroundImage: {
    position: 'absolute',
    width: '100%',
    height: '100%',
  },
  overlay: {
    position: 'absolute',
    width: '100%',
    height: '100%',
    backgroundColor: 'rgba(19, 19, 21, 0.65)', 
  },
  contentContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: 120,
    paddingBottom: 80,
    paddingHorizontal: 24,
    zIndex: 10,
  },
  brandContainer: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
  },
  logoContainer: {
    width: 120,
    height: 120,
    marginBottom: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoGlow: {
    position: 'absolute',
    width: '100%',
    height: '100%',
    backgroundColor: '#E6E6FA', 
    opacity: 0.3,
    borderRadius: 60,
    shadowColor: '#E6E6FA',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 30,
    elevation: 10,
  },
  logo: {
    width: '100%',
    height: '100%',
    resizeMode: 'contain',
    zIndex: 10,
  },
  appName: {
    fontSize: 48,
    color: '#FFFFFF',
    fontWeight: '300',
    letterSpacing: -1,
    textShadowColor: 'rgba(0, 0, 0, 0.5)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 10,
  },
  taglineWrapper: {
    height: 32,
    marginTop: 16,
    justifyContent: 'center',
  },
  tagline: {
    fontSize: 16,
    color: '#E6E6FA',
    fontWeight: '400',
    textAlign: 'center',
  },
  cursor: {
    color: '#e42b10', 
    fontWeight: 'bold',
  },
  loginContainer: {
    width: '100%',
    maxWidth: 400,
  },
  googleButton: {
    width: '100%',
    backgroundColor: 'rgba(32, 31, 33, 0.6)', 
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)', 
    borderRadius: 9999,
    paddingVertical: 16,
    overflow: 'hidden',
  },
  googleButtonPressed: {
    backgroundColor: 'rgba(230, 230, 250, 0.1)', 
    transform: [{ scale: 0.98 }],
  },
  buttonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  googleIcon: {
    fontSize: 20,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '400',
    letterSpacing: 0.5,
  }
});