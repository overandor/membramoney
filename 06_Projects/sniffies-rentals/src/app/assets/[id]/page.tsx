"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { membraAPI } from "@/lib/api";
import { MembraAsset, CATEGORY_LABELS } from "@/lib/types";
import { ArrowLeft, Shield, BadgeCheck, Clock, FileText, ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";

export default function AssetDetailPage() {
  const { id } = useParams();
  const [asset, setAsset] = useState<MembraAsset | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    membraAPI.getAsset(id as string)
      .then(setAsset)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex min-h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-400" />
      </div>
    );
  }

  if (!asset) {
    return (
      <div className="flex min-h-full flex-col items-center justify-center px-4">
        <p className="text-zinc-400">Asset not found</p>
        <Link href="/" className="mt-4 text-emerald-400">Back to map</Link>
      </div>
    );
  }

  const cat = CATEGORY_LABELS[asset.category] || { label: asset.category, icon: "📍" };
  const price = (asset.price_cents / 100).toFixed(2);

  return (
    <div className="flex min-h-full flex-col bg-zinc-950">
      <header className="sticky top-0 z-50 flex h-14 items-center gap-3 border-b border-zinc-800 bg-zinc-950/80 px-4 backdrop-blur-md">
        <Link href="/" className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900">
          <ArrowLeft className="h-4 w-4 text-zinc-400" />
        </Link>
        <h1 className="text-base font-bold">{asset.title}</h1>
      </header>

      <main className="flex-1 px-4 py-6">
        <div className="mb-4 flex h-48 w-full items-center justify-center rounded-xl bg-zinc-800 text-6xl">
          {cat.icon}
        </div>

        <div className="mb-4">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-zinc-800 px-2.5 py-0.5 text-xs text-zinc-400">{cat.label}</span>
            {asset.verified && <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs text-emerald-400">Verified</span>}
          </div>
          <h2 className="mt-2 text-xl font-bold text-zinc-100">{asset.title}</h2>
          <p className="mt-1 text-sm text-zinc-400">{asset.description}</p>
        </div>

        <div className="mb-4 flex items-center gap-3 border-y border-zinc-800 py-3">
          {asset.trust_badges?.includes("identity_verified") && (
            <div className="flex items-center gap-1 text-xs text-blue-400">
              <BadgeCheck className="h-3.5 w-3.5" />
              Identity Verified
            </div>
          )}
          {asset.verified && (
            <div className="flex items-center gap-1 text-xs text-emerald-400">
              <Shield className="h-3.5 w-3.5" />
              Insured Access
            </div>
          )}
        </div>

        {asset.rules && Object.keys(asset.rules).length > 0 && (
          <div className="mb-6">
            <h3 className="mb-2 text-sm font-semibold text-zinc-300">Rules</h3>
            <div className="space-y-2">
              {Object.entries(asset.rules).map(([k, v]) => (
                <div key={k} className="flex items-start gap-2 rounded-lg bg-zinc-900/50 p-2 text-xs text-zinc-400">
                  <FileText className="mt-0.5 h-3 w-3 shrink-0 text-zinc-500" />
                  <span className="capitalize">{k.replace(/_/g, " ")}: {String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <Link
          href={`/book/${asset.asset_id}`}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-500 py-3.5 text-sm font-bold uppercase tracking-wider text-zinc-950 hover:bg-emerald-400 transition-colors"
        >
          Book Access — ${price}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </main>
    </div>
  );
}
