"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Shirt, DollarSign, MapPin, Clock, CheckCircle, Shield, Camera, QrCode, ArrowLeft } from "lucide-react";
import { membraAPI } from "@/lib/api";

export default function WearOwnerPage() {
  const [earnings, setEarnings] = useState(142);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const camps = await membraAPI.listAdCampaigns("funded");
        setCampaigns(camps.slice(0, 3));
      } catch (e) {}
      setLoading(false);
    }
    load();
  }, []);

  const demoGarments = [
    { id: "g1", type: "hoodie", title: "Black hoodie", status: "assigned", campaign: "Joe's Pizza Launch", rate: 35 },
    { id: "g2", type: "tshirt", title: "White tee", status: "available", campaign: null, rate: 15 },
  ];

  return (
    <div className="flex min-h-full flex-col bg-[#080A0D]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-6 pb-4">
        <h1 className="text-lg font-bold text-[#F7F4EF]">Membra Wear</h1>
        <div className="flex items-center gap-1.5 rounded-full bg-[#121820] border border-[#2A3038] px-3 py-1.5">
          <DollarSign className="h-3.5 w-3.5 text-[#D6A85C]" />
          <span className="text-sm font-bold text-[#D6A85C]">${earnings}</span>
          <span className="text-[10px] text-[#9DA6B2]">earned</span>
        </div>
      </div>

      {/* My Garments */}
      <section className="px-4 pb-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">My Garments</h2>
        <div className="space-y-3">
          {demoGarments.map((g) => (
            <div key={g.id} className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-500/10">
                    <Shirt className="h-5 w-5 text-orange-400" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[#F7F4EF]">{g.title}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="flex items-center gap-1 text-[10px] text-[#27D17F]">
                        <Shield className="h-3 w-3" /> Certified
                      </span>
                      <span className="text-[10px] text-[#9DA6B2]">
                        {g.status === "assigned" ? (
                          <span className="text-orange-400">{g.campaign}</span>
                        ) : (
                          "Available"
                        )}
                      </span>
                    </div>
                  </div>
                </div>
                <span className="text-sm font-bold text-[#D6A85C]">${g.rate}/day</span>
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
              <div className="mt-3 space-y-1">
                <div className="flex items-center gap-2 text-[10px] text-[#9DA6B2]">
                  <MapPin className="h-3 w-3" /> {c.target_city}
                </div>
                <div className="flex items-center gap-2 text-[10px] text-[#9DA6B2]">
                  <Clock className="h-3 w-3" /> {c.start_date?.slice(0, 10)} → {c.end_date?.slice(0, 10)}
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs font-bold text-[#D6A85C]">${(c.budget_cents / 100).toFixed(0)} budget</span>
                <button className="rounded-lg bg-orange-500 px-3 py-1.5 text-xs font-bold text-zinc-950 hover:bg-orange-400 transition-colors">
                  Accept
                </button>
              </div>
            </div>
          )) : (
            <div className="rounded-xl border border-[#2A3038] bg-[#121820] p-4 text-center">
              <p className="text-sm text-[#9DA6B2]">No wear campaigns available.</p>
            </div>
          )}
        </div>
      </section>

      {/* Demo Campaign Offer */}
      <section className="px-4 pb-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">Campaign Offer</h2>
        <div className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
          <p className="text-sm font-bold text-[#F7F4EF]">Joe's Pizza Launch</p>
          <div className="mt-3 space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-[#9DA6B2]">Wear</span>
              <span className="text-[#F7F4EF]">Black hoodie</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-[#9DA6B2]">Area</span>
              <span className="text-[#F7F4EF]">Downtown Brooklyn</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-[#9DA6B2]">Time</span>
              <span className="text-[#F7F4EF]">12 PM – 4 PM</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-[#9DA6B2]">Payout</span>
              <span className="text-[#D6A85C] font-bold">$35/day</span>
            </div>
          </div>
          <div className="mt-3 border-t border-[#2A3038] pt-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#9DA6B2] mb-1.5">Requirements</p>
            <div className="space-y-1">
              {["Wear visible logo", "Stay in campaign zone", "Submit 2 proof photos", "Allow QR/NFC scans"].map((r) => (
                <div key={r} className="flex items-center gap-1.5 text-xs text-[#27D17F]">
                  <CheckCircle className="h-3 w-3" /> {r}
                </div>
              ))}
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <button className="flex-1 rounded-lg border border-[#2A3038] bg-[#080A0D] py-2.5 text-xs font-bold text-[#F7F4EF] hover:bg-[#1a2028] transition-colors">
              Decline
            </button>
            <button className="flex-1 rounded-lg bg-orange-500 py-2.5 text-xs font-bold text-zinc-950 hover:bg-orange-400 transition-colors">
              Accept
            </button>
          </div>
        </div>
      </section>

      {/* Quick Actions */}
      <section className="px-4 pb-8">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">Quick Actions</h2>
        <div className="grid grid-cols-2 gap-3">
          <Link href="/ads/wear/proof" className="flex flex-col items-center gap-2 rounded-xl border border-[#2A3038] bg-[#121820] p-4 hover:bg-[#1a2028] transition-colors">
            <Camera className="h-5 w-5 text-orange-400" />
            <span className="text-xs font-semibold text-[#F7F4EF]">Submit Proof</span>
          </Link>
          <Link href="/ads/owner" className="flex flex-col items-center gap-2 rounded-xl border border-[#2A3038] bg-[#121820] p-4 hover:bg-[#1a2028] transition-colors">
            <QrCode className="h-5 w-5 text-[#9DA6B2]" />
            <span className="text-xs font-semibold text-[#F7F4EF]">Window/Car</span>
          </Link>
        </div>
      </section>
    </div>
  );
}
