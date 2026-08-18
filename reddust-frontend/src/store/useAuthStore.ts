// src/store/useAuthStore.ts
import { create } from 'zustand';

interface AuthState {
  isAuthenticated: boolean;
  userInfo: any | null; // Holds Google profile data
  signIn: (user: any) => void;
  signOut: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false, 
  userInfo: null,
  signIn: (user) => set({ isAuthenticated: true, userInfo: user }),
  signOut: () => set({ isAuthenticated: false, userInfo: null }),
}));