//  src/store/useAppStore.ts

import { create } from 'zustand';

interface AppState {
  activePersona: 'sara' | 'syan';
  isSidebarOpen: boolean;
  currentTrack: any | null; // Replace 'any' with a Track type later
  isExpandedPlayerOpen: boolean;
  
  togglePersona: () => void;
  toggleSidebar: () => void;
  setTrack: (track: any | null) => void;
  toggleExpandedPlayer: (isOpen: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activePersona: 'sara',
  isSidebarOpen: false,
  currentTrack: { title: "Midnight Dust – Lo-Fi Sanctuary", artist: "RedDust Ambient" }, // Mock track for now
  isExpandedPlayerOpen: false,

  togglePersona: () => set((state) => ({ 
    activePersona: state.activePersona === 'sara' ? 'syan' : 'sara' 
  })),
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  setTrack: (track) => set({ currentTrack: track }),
  toggleExpandedPlayer: (isOpen) => set({ isExpandedPlayerOpen: isOpen }),
}));