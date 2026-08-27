// src/store/useAppStore.ts

import { create } from 'zustand';
import { Track } from 'react-native-track-player'; 

interface AppState {
  activePersona: 'sara' | 'syan';
  isSidebarOpen: boolean;
  currentTrack: Track | null;
  isExpandedPlayerOpen: boolean;
  
  togglePersona: () => void;
  toggleSidebar: () => void;
  setTrack: (track: Track | null) => void;
  toggleExpandedPlayer: (isOpen: boolean) => void;
  resetAppStore: () => void;
}

// We extract the initial state so we can easily reset it later
const initialState = {
  activePersona: 'sara' as const,
  isSidebarOpen: false,
  currentTrack: null,
  isExpandedPlayerOpen: false,
};

export const useAppStore = create<AppState>((set) => ({
  ...initialState,

  togglePersona: () => set((state) => ({ 
    activePersona: state.activePersona === 'sara' ? 'syan' : 'sara' 
  })),
  toggleSidebar: () => set((state) => ({ 
    isSidebarOpen: !state.isSidebarOpen 
  })),
  setTrack: (track) => set({ currentTrack: track }),
  toggleExpandedPlayer: (isOpen) => set({ isExpandedPlayerOpen: isOpen }),
  
  // This is called by useAuthStore.signOut()
  resetAppStore: () => set(initialState),
}));