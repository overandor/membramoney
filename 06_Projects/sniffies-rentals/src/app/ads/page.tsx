"use client";

import Link from "next/link";
import { Megaphone, Home, Car, QrCode, ArrowRight, DollarSign } from "lucide-react";

export default function AdsLandingPage() {
  return (
    <div className="flex min-h-full flex-col bg-[#080A0D]">
      {/* Hero */}
      <section className="flex flex-col items-center px-6 pt-10 pb-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-orange-500/10 mb-4">
          <Megaphone className="h-7 w-7 text-orange-400" />
        </div>
        <h1 className="text-2xl font-bold text-[#F7F4EF]">Membra Ads</h1>
        <p className="mt-2 max-w-xs text-sm text-[#9DA6B2]">
          Decentralized local ads on real windows and real cars. Verified placements. Paid owners. Proof for advertisers.
        </p>

        {/* CTAs */}
        <div className="mt-6 flex w-full max-w-sm flex-col gap-3">
          <Link
            href="/ads/owner"
            className="flex items-center justify-center gap-2 rounded-xl bg-orange-500 py-3.5 text-sm font-bold uppercase tracking-wider text-zinc-950 hover:bg-orange-400 transition-colors"
          >
            <Home className="h-4 w-4" />
            I own ad space
          </Link>
          <Link
            href="/ads/advertiser"
            className="flex items-center justify-center gap-2 rounded-xl border border-[#2A3038] bg-[#121820] py-3.5 text-sm font-bold uppercase tracking-wider text-[#F7F4EF] hover:bg-[#1a2028] transition-colors"
          >
            <Megaphone className="h-4 w-4" />
            I want to advertise
          </Link>
        </div>
      </section>

      {/* Pricing Cards */}
      <section className="px-4 pb-8">
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: Home, label: "Windows", range: "$5–$20/day", color: "text-[#D6A85C]" },
            { icon: Car, label: "Cars", range: "$3–$25/day", color: "text-[#FF6A00]" },
            { icon: QrCode, label: "Local QR", range: "Trackable", color: "text-[#27D17F]" },
          ].map((item) => (
            <div key={item.label} className="flex flex-col items-center rounded-xl border border-[#2A3038] bg-[#121820] p-4 text-center">
              <item.icon className={`h-5 w-5 ${item.color}`} />
              <p className="mt-2 text-xs font-semibold text-[#F7F4EF]">{item.label}</p>
              <p className="mt-1 text-[10px] text-[#9DA6B2]">{item.range}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="px-4 pb-8">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[#9DA6B2] mb-4">How it works</h2>
        <div className="space-y-3">
          {[
            { step: "1", title: "Owner lists space", desc: "Apartment window or car" },
            { step: "2", title: "Advertiser creates campaign", desc: "Choose neighborhood, budget, creative" },
            { step: "3", title: "Membra verifies", desc: "Creative review + placement proof" },
            { step: "4", title: "Owner gets paid", desc: "Daily payout after verified proof" },
          ].map((s) => (
            <div key={s.step} className="flex items-center gap-3 rounded-xl border border-[#2A3038] bg-[#121820] p-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-orange-500/10 text-xs font-bold text-orange-400">
                {s.step}
              </span>
              <div>
                <p className="text-sm font-semibold text-[#F7F4EF]">{s.title}</p>
                <p className="text-xs text-[#9DA6B2]">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Footer pitch */}
      <section className="px-4 pb-8 text-center">
        <p className="text-xs text-[#9DA6B2]">
          Membra turns apartment windows and everyday cars into a verified local media network.
        </p>
      </section>
    </div>
  );
}
