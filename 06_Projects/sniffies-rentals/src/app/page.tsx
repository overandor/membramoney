"use client";

import { useEffect } from "react";
import { Navbar } from "@/components/Navbar";
import { CategoryFilter } from "@/components/CategoryFilter";
import { AssetCard } from "@/components/AssetCard";
import { AssetDrawer } from "@/components/AssetDrawer";
import { useMembraStore } from "@/store/membra";
import { MapPin, Loader2 } from "lucide-react";
import Link from "next/link";

export default function Home() {
  const { assets, selectedAsset, setSelectedAsset, selectedCategory, loadAssets, getFilteredAssets, loading, error } = useMembraStore();
  const filtered = getFilteredAssets();

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  return (
    <div className="flex flex-col min-h-full">
      <Navbar />
      <CategoryFilter />

      <main className="flex-1 px-4 py-4">
        {/* Map Section */}
        <div className="mb-4">
          <div className="mb-2 flex items-center gap-2">
            <MapPin className="h-4 w-4 text-emerald-400" />
            <h2 className="text-sm font-semibold text-zinc-300">
              Nearby Access Points ({filtered.length})
            </h2>
          </div>
          <div className="relative h-64 w-full overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900">
            <div className="absolute inset-0 opacity-20">
              <svg width="100%" height="100%"><defs><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-zinc-500"/></pattern></defs><rect width="100%" height="100%" fill="url(#grid)"/></svg>
            </div>
            <div className="absolute inset-4 opacity-10"><div className="h-full w-full rounded-lg border-2 border-dashed border-zinc-500"/></div>
            <div className="absolute bottom-2 right-2 rounded bg-zinc-950/60 px-1.5 py-0.5 text-[10px] text-zinc-500">Map</div>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="h-6 w-6 animate-spin text-emerald-400" />
            <span className="ml-2 text-sm text-zinc-400">Loading access points...</span>
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-800 bg-red-900/20 p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Listings */}
        <div className="space-y-3 pb-20">
          {filtered.map((asset) => (
            <AssetCard
              key={asset.asset_id}
              asset={asset}
              isSelected={selectedAsset?.asset_id === asset.asset_id}
              onClick={() =>
                setSelectedAsset(selectedAsset?.asset_id === asset.asset_id ? null : asset)
              }
            />
          ))}
        </div>
      </main>

      {/* Floating Action Button */}
      <Link
        href="/list"
        className="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-6 py-3 text-sm font-bold uppercase tracking-wider text-zinc-950 shadow-lg shadow-emerald-500/20 hover:bg-emerald-400 transition-colors"
      >
        List Your Asset
      </Link>

      {/* Detail Drawer */}
      <AssetDrawer />
    </div>
  );
}
