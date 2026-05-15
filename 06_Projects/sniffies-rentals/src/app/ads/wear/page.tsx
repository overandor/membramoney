"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Shirt, DollarSign, MapPin, Clock, CheckCircle, ArrowRight } from "lucide-react";
import { membraAPI } from "@/lib/api";

export default function WearLandingPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);

  useEffect(() => {
    membraAPI.listAdCampaigns("funded").then(setCampaigns).catch(() => {});
  }, []);

  return (
    <div className="flex min-h-full flex-col bg-[#080A0D]">
      {/* Hero */}
      <section className="flex flex-col items-center px-6 pt-10 pb-6 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-orange-500/10 mb-4">
          <Shirt className="h-7 w-7 text-orange-400" />
        </div>
        <h1 className="text-2xl font-bold text-[#F7F4EF]">Membra Wear</h1>
        <p className="mt-2 max-w-xs text-sm text-[#9DA6B2]">
          Get paid to wear certified ad clothing in approved locations and time windows.
        </p>
        <div className="mt-6 flex w-full max-w-sm gap-3">
          <Link
            href="/ads/wear/owner"
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-orange-500 py-3.5 text-sm font-bold uppercase tracking-wider text-zinc-950 hover:bg-orange-400 transition-colors"
          >
            <Shirt className="h-4 w-4" />
            I want to wear
          </Link>
          <Link
            href="/ads/advertiser"
            className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-[#2A3038] bg-[#121820] py-3.5 text-sm font-bold uppercase tracking-wider text-[#F7F4EF] hover:bg-[#1a2028] transition-colors"
          >
            <DollarSign className="h-4 w-4" />
            Advertise
          </Link>
        </div>
      </section>

      {/* Pricing */}
      <section className="px-4 pb-4">
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: Shirt, label: "T-shirt", range: "$5–$20/day", color: "text-orange-400" },
            { icon: Shirt, label: "Hoodie", range: "$15–$50/day", color: "text-[#D6A85C]" },
            { icon: DollarSign, label: "Event", range: "$30–$150/day", color: "text-[#27D17F]" },
          ].map((item) => (
            <div key={item.label} className="flex flex-col items-center rounded-xl border border-[#2A3038] bg-[#121820] p-4 text-center">
              <item.icon className={`h-5 w-5 ${item.color}`} />
              <p className="mt-2 text-xs font-semibold text-[#F7F4EF]">{item.label}</p>
              <p className="mt-1 text-[10px] text-[#9DA6B2]">{item.range}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Rules */}
      <section className="px-4 pb-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">Core Rules</h2>
        <div className="space-y-2">
          {[
            "No identity verification → no campaign",
            "No approved clothing → no payout",
            "No proof-of-wear → no payout",
            "No location/time match → no payout",
          ].map((rule) => (
            <div key={rule} className="flex items-center gap-2 rounded-lg border border-[#2A3038] bg-[#121820] px-3 py-2">
              <CheckCircle className="h-3.5 w-3.5 text-orange-400" />
              <span className="text-xs text-[#F7F4EF]">{rule}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Available Campaigns */}
      <section className="px-4 pb-8">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#9DA6B2] mb-3">Available Wear Campaigns</h2>
        <div className="space-y-3">
          {campaigns.length > 0 ? campaigns.map((c) => (
            <div key={c.campaign_id} className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
              <p className="text-sm font-semibold text-[#F7F4EF]">{c.title}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <span className="flex items-center gap-1 rounded bg-[#080A0D] px-2 py-1 text-[10px] text-[#9DA6B2]">
                  <MapPin className="h-3 w-3" /> {c.target_city}
                </span>
                <span className="flex items-center gap-1 rounded bg-[#080A0D] px-2 py-1 text-[10px] text-[#9DA6B2]">
                  <Clock className="h-3 w-3" /> {c.asset_types?.join(", ")}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs font-bold text-[#D6A85C]">${(c.budget_cents / 100).toFixed(0)} budget</span>
                <Link
                  href="/ads/wear/owner"
                  className="flex items-center gap-1 rounded-lg bg-orange-500 px-3 py-1.5 text-xs font-bold text-zinc-950 hover:bg-orange-400 transition-colors"
                >
                  Accept <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </div>
          )) : (
            <div className="rounded-xl border border-[#2A3038] bg-[#121820] p-6 text-center">
              <p className="text-sm text-[#9DA6B2]">No wear campaigns in your area yet.</p>
              <p className="text-xs text-[#9DA6B2] mt-1">Check back soon or browse window/car campaigns.</p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
