"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, TrendingUp, MapPin, Megaphone, Eye, DollarSign, QrCode } from "lucide-react";
import { membraAPI } from "@/lib/api";

export default function AdsAdvertiserPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const camps = await membraAPI.listAdCampaigns();
        setCampaigns(camps);
        if (camps.length > 0) {
          const a = await membraAPI.getAdCampaignAnalytics(camps[0].campaign_id);
          setAnalytics(a);
        }
      } catch (e) {}
      setLoading(false);
    }
    load();
  }, []);

  return (
    <div className="flex min-h-full flex-col bg-[#080A0D]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-6 pb-4">
        <h1 className="text-lg font-bold text-[#F7F4EF]">Advertiser Dashboard</h1>
        <Link
          href="/ads/campaigns/new"
          className="flex items-center gap-1.5 rounded-lg bg-orange-500 px-3 py-1.5 text-xs font-bold text-zinc-950 hover:bg-orange-400 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          New Campaign
        </Link>
      </div>

      {/* Active Campaigns */}
      <section className="px-4 pb-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">Active Campaigns</h2>
        <div className="space-y-3">
          {campaigns.length > 0 ? campaigns.map((c) => (
            <div key={c.campaign_id} className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-[#F7F4EF]">{c.title}</p>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                  c.status === "active" || c.status === "launched" ? "bg-green-500/10 text-green-400" :
                  c.status === "funded" ? "bg-orange-500/10 text-orange-400" :
                  "bg-zinc-800 text-zinc-400"
                }`}>
                  {c.status}
                </span>
              </div>
              <p className="text-xs text-[#9DA6B2] mt-1">{c.target_city} · {c.asset_types?.join(", ")}</p>
              <div className="mt-3 grid grid-cols-3 gap-2">
                <div className="rounded-lg bg-[#080A0D] p-2 text-center">
                  <p className="text-xs font-bold text-[#F7F4EF]">${(c.budget_cents / 100).toFixed(0)}</p>
                  <p className="text-[10px] text-[#9DA6B2]">Budget</p>
                </div>
                <div className="rounded-lg bg-[#080A0D] p-2 text-center">
                  <p className="text-xs font-bold text-[#27D17F]">{analytics?.total_placements || 0}</p>
                  <p className="text-[10px] text-[#9DA6B2]">Placements</p>
                </div>
                <div className="rounded-lg bg-[#080A0D] p-2 text-center">
                  <p className="text-xs font-bold text-[#D6A85C]">{analytics?.total_scans || 0}</p>
                  <p className="text-[10px] text-[#9DA6B2]">Scans</p>
                </div>
              </div>
            </div>
          )) : (
            <div className="rounded-xl border border-[#2A3038] bg-[#121820] p-6 text-center">
              <Megaphone className="mx-auto h-8 w-8 text-orange-400 mb-2" />
              <p className="text-sm font-semibold text-[#F7F4EF]">No campaigns yet</p>
              <p className="text-xs text-[#9DA6B2] mt-1">Create your first local ad campaign.</p>
              <Link
                href="/ads/campaigns/new"
                className="mt-3 inline-flex items-center gap-1 rounded-lg bg-orange-500 px-4 py-2 text-xs font-bold text-zinc-950 hover:bg-orange-400 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                Create Campaign
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* Inventory nearby */}
      <section className="px-4 pb-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">Inventory Nearby</h2>
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: Eye, count: 186, label: "Windows", color: "text-[#D6A85C]" },
            { icon: Car, count: 421, label: "Cars", color: "text-orange-400" },
            { icon: MapPin, count: 12, label: "Blocks", color: "text-[#27D17F]" },
          ].map((item) => (
            <div key={item.label} className="flex flex-col items-center rounded-xl border border-[#2A3038] bg-[#121820] p-3 text-center">
              <item.icon className={`h-4 w-4 ${item.color}`} />
              <p className="mt-1 text-sm font-bold text-[#F7F4EF]">{item.count}</p>
              <p className="text-[10px] text-[#9DA6B2]">{item.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Analytics teaser */}
      {analytics && (
        <section className="px-4 pb-8">
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">Performance</h2>
          <div className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-[#F7F4EF]">Top Campaign</p>
              <TrendingUp className="h-4 w-4 text-[#27D17F]" />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-[#9DA6B2]">Verified proofs</span>
                <span className="text-[#F7F4EF] font-semibold">{analytics.verified_proofs} / {analytics.total_proofs}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-[#9DA6B2]">QR scans</span>
                <span className="text-[#F7F4EF] font-semibold">{analytics.total_scans}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-[#9DA6B2]">Payouts released</span>
                <span className="text-[#D6A85C] font-semibold">${(analytics.total_released_cents / 100).toFixed(2)}</span>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function Car(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/>
    </svg>
  );
}
