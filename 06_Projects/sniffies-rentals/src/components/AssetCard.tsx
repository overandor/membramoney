"use client";

import { MembraAsset, CATEGORY_LABELS } from "@/lib/types";
import { Shield, BadgeCheck, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";

export function AssetCard({
  asset,
  isSelected,
  onClick,
}: {
  asset: MembraAsset;
  isSelected: boolean;
  onClick: () => void;
}) {
  const cat = CATEGORY_LABELS[asset.category] || { label: asset.category, icon: "📍" };
  const priceDollars = (asset.price_cents / 100).toFixed(2);

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full gap-3 rounded-xl border p-3 text-left transition-all",
        isSelected
          ? "border-emerald-500/40 bg-emerald-500/5 shadow-lg shadow-emerald-500/5"
          : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700 hover:bg-zinc-900"
      )}
    >
      <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-zinc-800 text-2xl">
        {cat.icon}
      </div>

      <div className="flex flex-1 flex-col justify-between py-0.5">
        <div>
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-sm font-semibold leading-tight text-zinc-100 line-clamp-1">
              {asset.title}
            </h3>
          </div>
          <p className="mt-0.5 text-xs text-zinc-500">{cat.label}</p>
        </div>

        <div className="mt-1 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            {asset.trust_badges?.includes("identity_verified") && (
              <BadgeCheck className="h-3.5 w-3.5 text-blue-400" />
            )}
            {asset.verified && (
              <Shield className="h-3.5 w-3.5 text-emerald-400" />
            )}
          </div>
          <span className="text-sm font-bold text-emerald-400">${priceDollars}</span>
        </div>
      </div>
    </button>
  );
}
