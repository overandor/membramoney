import { create } from "zustand";
import { MembraAsset, MembraVisit, MembraParty } from "@/lib/types";
import { membraAPI } from "@/lib/api";

interface MembraStore {
  // Mode
  appMode: "access" | "ads";
  setAppMode: (mode: "access" | "ads") => void;

  // User
  currentUser: MembraParty | null;
  setCurrentUser: (user: MembraParty | null) => void;

  // Assets
  assets: MembraAsset[];
  selectedAsset: MembraAsset | null;
  selectedCategory: string;
  setAssets: (assets: MembraAsset[]) => void;
  setSelectedAsset: (asset: MembraAsset | null) => void;
  setSelectedCategory: (category: string) => void;
  loadAssets: () => Promise<void>;
  getFilteredAssets: () => MembraAsset[];

  // Visits
  currentVisit: MembraVisit | null;
  setCurrentVisit: (visit: MembraVisit | null) => void;

  // Ads
  adCampaigns: any[];
  setAdCampaigns: (campaigns: any[]) => void;
  adPlacements: any[];
  setAdPlacements: (placements: any[]) => void;

  // UI
  loading: boolean;
  error: string | null;
  setLoading: (v: boolean) => void;
  setError: (v: string | null) => void;
}

export const useMembraStore = create<MembraStore>((set, get) => ({
  appMode: "access",
  setAppMode: (mode) => set({ appMode: mode }),

  currentUser: null,
  setCurrentUser: (user) => set({ currentUser: user }),

  assets: [],
  selectedAsset: null,
  selectedCategory: "All",
  setAssets: (assets) => set({ assets }),
  setSelectedAsset: (asset) => set({ selectedAsset: asset }),
  setSelectedCategory: (category) => set({ selectedCategory: category }),
  loadAssets: async () => {
    set({ loading: true, error: null });
    try {
      const data = await membraAPI.listAssets();
      set({ assets: data });
    } catch (e: any) {
      set({ error: e.message });
    } finally {
      set({ loading: false });
    }
  },
  getFilteredAssets: () => {
    const { assets, selectedCategory } = get();
    if (selectedCategory === "All") return assets;
    return assets.filter((a) => a.category === selectedCategory);
  },

  currentVisit: null,
  setCurrentVisit: (visit) => set({ currentVisit: visit }),

  adCampaigns: [],
  setAdCampaigns: (campaigns) => set({ adCampaigns: campaigns }),
  adPlacements: [],
  setAdPlacements: (placements) => set({ adPlacements: placements }),

  loading: false,
  error: null,
  setLoading: (v) => set({ loading: v }),
  setError: (v) => set({ error: v }),
}));
