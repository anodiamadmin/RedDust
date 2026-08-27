// src/store/useAuthStore.ts

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { GoogleSignin, User } from '@react-native-google-signin/google-signin';
import { useAppStore } from './useAppStore'; // Import AppStore to reset it on logout

interface AuthState {
  isAuthenticated: boolean;
  userInfo: User | null; // <-- Replaced 'any' with the OFFICIAL Google User type
  signIn: (user: User) => void;
  signOut: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isAuthenticated: false, 
      userInfo: null,
      
      signIn: (user) => set({ isAuthenticated: true, userInfo: user }),
      
      signOut: async () => {
        try {
          // Attempt to clear Google session
          await GoogleSignin.signOut(); 
        } catch (error) {
          console.error("Error signing out from Google: ", error);
          // We don't throw here; we still want to clear local state even if offline
        }
        
        // 1. Clear local Auth state
        set({ isAuthenticated: false, userInfo: null });
        
        // 2. Clear local App state (Prevents data leaking to the next user)
        useAppStore.getState().resetAppStore();
      },
    }),
    {
      name: 'reddust-auth-storage', 
      storage: createJSONStorage(() => AsyncStorage), 
    }
  )
);