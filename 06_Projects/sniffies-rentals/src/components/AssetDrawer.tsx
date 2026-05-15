"use client";

import { useMembraStore } from "@/store/membra";
import { CATEGORY_LABELS } from "@/lib/types";
import { X, Shield, BadgeCheck, Clock, FileText, Lock, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";

export function AssetDrawer() {
  const { selectedAsset, setSelectedAsset } = useMembraStore();

  if (!selectedAsset) return null;

  const cat = CATEGORY_LABELS[selectedAsset.category] || { label: selectedAsset.category, icon: "📍" };
  const priceDollars = (selectedAsset.price_cents / 100).toFixed(2);

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center">
      <div className="absolute inset-0 bg-zinc-950/60 backdrop-blur-sm" onClick={() => setSelectedAsset(null)} />
      <div className="relative w-full max-w-lg rounded-t-2xl border border-zinc-800 bg-zinc-900 shadow-2xl animate-in slide-in-from-bottom duration-300">
        <div className="flex justify-center pt-3 pb-1">
          <div className="h-1 w-10 rounded-full bg-zinc-700" />
        </div>
        <button onClick={() => setSelectedAsset(null)} className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-zinc-800 hover:bg-zinc-700 transition-colors">
          <X className="h-4 w-4 text-zinc-400" />
        </button>

        <div className="max-h-[80vh] overflow-y-auto px-4 pb-6">
          <div className="mb-4 flex h-48 w-full items-center justify-center rounded-xl bg-zinc-800 text-6xl">
            {cat.icon}
          </div>

          <div className="mb-4">
            <h2 className="text-xl font-bold text-zinc-100">{selectedAsset.title}</h2>
            <p className="mt-1 text-sm text-zinc-400">{cat.label} access point</p>
            <div className="mt-2 flex items-center gap-2">
              <span className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-3 py-1 text-sm font-semibold text-emerald-400">
                <Clock className="h-3.5 w-3.5" />
                ${priceDollars}
              </span>
            </div>
          </div>

          <div className="mb-4 flex items-center gap-3 border-y border-zinc-800 py-3">
            {selectedAsset.trust_badges?.includes("identity_verified") && (
              <div className="flex items-center gap-1 text-xs text-blue-400">
                <BadgeCheck className="h-3.5 w-3.5" />
                Identity Verified
              </div>
            )}
            {selectedAsset.verified && (
              <div className="flex items-center gap-1 text-xs text-emerald-400">
                <Shield className="h-3.5 w-3.5" />
                Insured Access
              </div>
            )}
            <div className="flex items-center gap-1 text-xs text-zinc-500">
              <Lock className="h-3.5 w-3.5" />
              QR Gate
            </div>
          </div>

          {selectedAsset.description && (
            <div className="mb-4">
              <h3 className="mb-1 text-sm font-semibold text-zinc-300">About</h3>
              <p className="text-sm leading-relaxed text-zinc-400">{selectedAsset.description}</p>
            </div>
          )}

          {selectedAsset.rules && Object.keys(selectedAsset.rules).length > 0 && (
            <div className="mb-4">
              <h3 className="mb-1 text-sm font-semibold text-zinc-300">Rules</h3>
              <div className="space-y-1">
                {Object.entries(selectedAsset.rules).map(([k, v]) => (
                  <div key={k} className="flex items-start gap-2 text-xs text-zinc-400">
                    <FileText className="mt-0.5 h-3 w-3 shrink-0 text-zinc-500" />
                    <span className="capitalize">{k.replace(/_/g, " ")}: {String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <Link
            href={`/book/${selectedAsset.asset_id}`}
            className={cn(
              "flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-sm font-bold uppercase tracking-wider transition-colors",
              "bg-emerald-500 text-zinc-950 hover:bg-emerald-400"
            )}
          >
            Book Access
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}
