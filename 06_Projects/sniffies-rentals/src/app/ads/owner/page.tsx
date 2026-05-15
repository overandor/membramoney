"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Home, Car, DollarSign, CheckCircle, Clock, Camera, Shield, Shirt } from "lucide-react";
import { membraAPI } from "@/lib/api";

export default function AdsOwnerPage() {
  const [earnings, setEarnings] = useState(142);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [placements, setPlacements] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const camps = await membraAPI.listAdCampaigns("funded");
        setCampaigns(camps.slice(0, 3));
        const plcs = await membraAPI.listPlacements({ owner_id: "usr_test" });
        setPlacements(plcs);
      } catch (e) {}
      setLoading(false);
    }
    load();
  }, []);

  const demoSpaces = [
    { id: "space_1", type: "window", title: "First-floor window", status: "live", rate: 12, icon: Home },
    { id: "space_2", type: "vehicle", title: "Rear car window", status: "available", rate: 6, icon: Car },
  ];

  return (
    <div className="flex min-h-full flex-col bg-[#080A0D]">
      {/* Earnings header */}
      <div className="px-4 pt-6 pb-4">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold text-[#F7F4EF]">Your Dashboard</h1>
          <div className="flex items-center gap-1.5 rounded-full bg-[#121820] border border-[#2A3038] px-3 py-1.5">
            <DollarSign className="h-3.5 w-3.5 text-[#D6A85C]" />
            <span className="text-sm font-bold text-[#D6A85C]">${earnings}</span>
            <span className="text-[10px] text-[#9DA6B2]">this month</span>
          </div>
        </div>
      </div>

      {/* My Ad Spaces */}
      <section className="px-4 pb-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">My Ad Spaces</h2>
        <div className="space-y-3">
          {demoSpaces.map((space) => (
            <div key={space.id} className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-500/10">
                    <space.icon className="h-5 w-5 text-orange-400" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[#F7F4EF]">{space.title}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="flex items-center gap-1 text-[10px] text-[#27D17F]">
                        <Shield className="h-3 w-3" /> Verified
                      </span>
                      <span className="text-[10px] text-[#9DA6B2]">
                        {space.status === "live" ? (
                          <span className="flex items-center gap-1 text-orange-400">
                            <Clock className="h-3 w-3" /> 1 campaign live
                          </span>
                        ) : (
                          "Available"
                        )}
                      </span>
                    </div>
                  </div>
                </div>
                <span className="text-sm font-bold text-[#D6A85C]">${space.rate}/day</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Available Campaigns */}
      <section className="px-4 pb-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">Available Campaigns</h2>
        <div className="space-y-3">
          {campaigns.length > 0 ? campaigns.map((c) => (
            <div key={c.campaign_id} className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
              <p className="text-sm font-semibold text-[#F7F4EF]">{c.title}</p>
              <p className="text-xs text-[#9DA6B2] mt-1">{c.target_city} · {c.asset_types?.join(", ")}</p>
              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-[#D6A85C]">${(c.budget_cents / 100).toFixed(0)} budget</span>
                <button className="rounded-lg bg-orange-500 px-3 py-1.5 text-xs font-bold text-zinc-950 hover:bg-orange-400 transition-colors">
                  Review
                </button>
              </div>
            </div>
          )) : (
            <div className="rounded-xl border border-[#2A3038] bg-[#121820] p-4 text-center">
              <p className="text-sm text-[#9DA6B2]">No campaigns available in your area yet.</p>
            </div>
          )}
        </div>
      </section>

      {/* Earn With tabs */}
      <section className="px-4 pb-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">Earn With</h2>
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Window", href: "/ads/owner", active: true, icon: Home },
            { label: "Car", href: "/ads/owner", active: false, icon: Car },
            { label: "Clothing", href: "/ads/wear/owner", active: false, icon: Shirt },
          ].map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className={`flex flex-col items-center gap-1.5 rounded-xl border p-3 transition-colors ${
                item.active
                  ? "border-orange-500/30 bg-orange-500/5"
                  : "border-[#2A3038] bg-[#121820] hover:bg-[#1a2028]"
              }`}
            >
              <item.icon className={`h-4 w-4 ${item.active ? "text-orange-400" : "text-[#9DA6B2]"}`} />
              <span className={`text-[10px] font-semibold ${item.active ? "text-orange-400" : "text-[#9DA6B2]"}`}>{item.label}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Quick Actions */}
      <section className="px-4 pb-8">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">Quick Actions</h2>
        <div className="grid grid-cols-2 gap-3">
          <Link href="/ads/proof" className="flex flex-col items-center gap-2 rounded-xl border border-[#2A3038] bg-[#121820] p-4 hover:bg-[#1a2028] transition-colors">
            <Camera className="h-5 w-5 text-orange-400" />
            <span className="text-xs font-semibold text-[#F7F4EF]">Submit Proof</span>
          </Link>
          <Link href="/ads/earnings" className="flex flex-col items-center gap-2 rounded-xl border border-[#2A3038] bg-[#121820] p-4 hover:bg-[#1a2028] transition-colors">
            <DollarSign className="h-5 w-5 text-[#D6A85C]" />
            <span className="text-xs font-semibold text-[#F7F4EF]">Earnings</span>
          </Link>
        </div>
      </section>
    </div>
  );
}
