// src/app/signin.tsx

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Image } from 'react-native';
import Animated, { 
  useSharedValue, 
  useAnimatedStyle, 
  withTiming, 
  withDelay, 
  Easing 
} from 'react-native-reanimated';

import GoogleSignInButton from '../components/GoogleSignInButton';

let hasPlayedAnimationThisSession = false;

export default function SigninScreen() {
  const fullTagline = "Listen to the music that listens to your soul";
  
  // --- Initialize React States ---
  // If animation already played, instantly show the full text and make button interactable
  const [displayedTagline, setDisplayedTagline] = useState(
    hasPlayedAnimationThisSession ? fullTagline : ''
  );
  const [showCursor, setShowCursor] = useState(false);
  const [isButtonInteractable, setIsButtonInteractable] = useState(
    hasPlayedAnimationThisSession
  );

  // --- Initialize Shared Values ---
  // If animation already played, instantly set them to their final destinations
  const bgScale = useSharedValue(hasPlayedAnimationThisSession ? 1.15 : 1);
  const bgTranslateY = useSharedValue(hasPlayedAnimationThisSession ? -20 : 0);
  const nameOpacity = useSharedValue(hasPlayedAnimationThisSession ? 1 : 0);
  const brandTranslateY = useSharedValue(hasPlayedAnimationThisSession ? -32 : 32); 
  const buttonOpacity = useSharedValue(hasPlayedAnimationThisSession ? 1 : 0);
  const buttonTranslateY = useSharedValue(hasPlayedAnimationThisSession ? 0 : 50); 

  useEffect(() => {
    if (hasPlayedAnimationThisSession) return;

    let typingTimeoutId: ReturnType<typeof setTimeout>;
    let typingIntervalId: ReturnType<typeof setInterval>;

    bgScale.value = withTiming(1.15, { duration: 15000, easing: Easing.out(Easing.quad) });
    bgTranslateY.value = withTiming(-20, { duration: 15000, easing: Easing.out(Easing.quad) });

    nameOpacity.value = withDelay(1000, withTiming(1, { duration: 1000 }));
    brandTranslateY.value = withDelay(2500, withTiming(-32, { duration: 1000, easing: Easing.out(Easing.exp) }));

    typingTimeoutId = setTimeout(() => {
      setShowCursor(true);
      let i = 0;
      typingIntervalId = setInterval(() => {
        setDisplayedTagline(fullTagline.slice(0, i + 1));
        i++;
        
        if (i >= fullTagline.length) {
          clearInterval(typingIntervalId);
          setShowCursor(false);
          
          setIsButtonInteractable(true);
          
          buttonOpacity.value = withTiming(1, { duration: 800 });
          buttonTranslateY.value = withTiming(0, { duration: 800, easing: Easing.out(Easing.back(1.5)) });
          hasPlayedAnimationThisSession = true;
        }
      }, 40); 
    }, 3300);

    return () => {
      clearTimeout(typingTimeoutId);
      if (typingIntervalId) clearInterval(typingIntervalId);
    };
  }, []);

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
      <Animated.Image 
        source={require('../../assets/images/splash-screen.jpg')} 
        style={[styles.backgroundImage, animatedBgStyle]}
        resizeMode="cover"
      />
      
      <View style={styles.overlay} />

      <View style={styles.contentContainer}>
        <Animated.View style={[styles.brandContainer, animatedBrandContainerStyle]}>
          <View style={styles.logoContainer}>
            <View style={styles.logoGlow} />
            <Image source={require('../../assets/images/logo.png')} style={styles.logo} />
          </View>

          <Animated.Text style={[styles.appName, animatedNameStyle]}>
            RedDust
          </Animated.Text>

          <View style={styles.taglineWrapper}>
            <Text style={styles.tagline}>
              {displayedTagline}
              {showCursor ? <Text style={styles.cursor}>|</Text> : null}
            </Text>
          </View>
        </Animated.View>

        <Animated.View 
          style={[styles.loginContainer, animatedButtonStyle]}
          pointerEvents={isButtonInteractable ? "auto" : "none"}
        >
          <GoogleSignInButton />
        </Animated.View>

      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#131315' },
  backgroundImage: { position: 'absolute', width: '100%', height: '100%' },
  overlay: { position: 'absolute', width: '100%', height: '100%', backgroundColor: 'rgba(19, 19, 21, 0.65)' },
  contentContainer: { flex: 1, alignItems: 'center', justifyContent: 'space-between', paddingTop: 120, paddingBottom: 80, paddingHorizontal: 24, zIndex: 10 },
  brandContainer: { alignItems: 'center', flex: 1, justifyContent: 'center' },
  logoContainer: { width: 120, height: 120, marginBottom: 24, justifyContent: 'center', alignItems: 'center' },
  logoGlow: { position: 'absolute', width: '100%', height: '100%', backgroundColor: '#E6E6FA', opacity: 0.3, borderRadius: 60 },
  logo: { width: '100%', height: '100%', resizeMode: 'contain', zIndex: 10 },
  appName: { fontSize: 48, color: '#FFFFFF', fontWeight: '300', letterSpacing: -1 },
  taglineWrapper: { height: 32, marginTop: 16, justifyContent: 'center' },
  tagline: { fontSize: 16, color: '#E6E6FA', fontWeight: '400', textAlign: 'center' },
  cursor: { color: '#e42b10', fontWeight: 'bold' },
  loginContainer: { width: '100%', maxWidth: 400, alignItems: 'center' }
});