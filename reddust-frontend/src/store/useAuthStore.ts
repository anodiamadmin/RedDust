// src/store/useAuthStore.ts

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { GoogleSignin } from '@react-native-google-signin/google-signin';

interface AuthState {
  isAuthenticated: boolean;
  userInfo: any | null; // Holds Google profile data
  signIn: (user: any) => void;
  signOut: () => Promise<void>; // 1. Make this return a Promise since native signout is async
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isAuthenticated: false, 
      userInfo: null,
      signIn: (user) => set({ isAuthenticated: true, userInfo: user }),
      
      // 2. Make signOut async and call GoogleSignin.signOut()
      signOut: async () => {
        try {
          // This forces Google to forget the session and show the account picker next time
          await GoogleSignin.signOut(); 
        } catch (error) {
          console.error("Error signing out from Google: ", error);
        }
        
        // Clear local Zustand state after Google confirms sign out
        set({ isAuthenticated: false, userInfo: null });
      },
    }),
    {
      name: 'reddust-auth-storage', // Unique storage key name
      storage: createJSONStorage(() => AsyncStorage), // Persists to device storage
    }
  )
);