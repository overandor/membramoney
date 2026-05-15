"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Megaphone, MapPin, DollarSign, Calendar, Upload, CheckCircle } from "lucide-react";
import Link from "next/link";
import { membraAPI } from "@/lib/api";

export default function CampaignBuilderPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [title, setTitle] = useState("");
  const [city, setCity] = useState("");
  const [neighborhoods, setNeighborhoods] = useState("");
  const [assetTypes, setAssetTypes] = useState<string[]>(["window", "vehicle"]);
  const [budget, setBudget] = useState(1000);
  const [duration, setDuration] = useState(7);
  const [loading, setLoading] = useState(false);
  const [campaignId, setCampaignId] = useState("");

  async function handleCreate() {
    setLoading(true);
    try {
      const start = new Date();
      const end = new Date(start.getTime() + duration * 24 * 60 * 60 * 1000);
      const campaign = await membraAPI.createAdCampaign({
        advertiser_id: "adv_demo",
        title,
        description: "",
        target_city: city,
        target_neighborhoods: neighborhoods.split(",").map((n) => n.trim()).filter(Boolean),
        asset_types: assetTypes,
        budget_cents: budget * 100,
        daily_budget_cents: Math.round((budget * 100) / duration),
        start_date: start.toISOString(),
        end_date: end.toISOString(),
        destination_url: "https://example.com",
        payout_rules: { window: 1200, vehicle: 800 },
      });
      setCampaignId(campaign.campaign_id);
      setStep(2);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleFund() {
    if (!campaignId) return;
    setLoading(true);
    try {
      await membraAPI.fundCampaign(campaignId);
      setStep(3);
      setTimeout(() => router.push("/ads/advertiser"), 1500);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-full flex-col bg-[#080A0D]">
      <header className="sticky top-0 z-50 flex h-14 items-center gap-3 border-b border-[#2A3038] bg-[#080A0D]/80 px-4 backdrop-blur-md">
        <Link href="/ads/advertiser" className="flex h-8 w-8 items-center justify-center rounded-full bg-[#121820]">
          <ArrowLeft className="h-4 w-4 text-[#9DA6B2]" />
        </Link>
        <h1 className="text-base font-bold text-[#F7F4EF]">Create Campaign</h1>
      </header>

      <main className="flex-1 px-4 py-6">
        {/* Progress */}
        <div className="mb-6 flex gap-2">
          {[1, 2, 3].map((s) => (
            <div key={s} className={`h-1.5 flex-1 rounded-full ${s <= step ? "bg-orange-500" : "bg-[#2A3038]"}`} />
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-5">
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-[#9DA6B2]">Campaign name</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Joe's Pizza Grand Opening"
                className="w-full rounded-lg border border-[#2A3038] bg-[#121820] px-3 py-2.5 text-sm text-[#F7F4EF] placeholder-[#9DA6B2]/50 focus:border-orange-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-[#9DA6B2]">Target area</label>
              <div className="flex items-center gap-2 rounded-lg border border-[#2A3038] bg-[#121820] px-3">
                <MapPin className="h-4 w-4 text-[#9DA6B2]" />
                <input
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="Williamsburg, Brooklyn"
                  className="flex-1 bg-transparent py-2.5 text-sm text-[#F7F4EF] placeholder-[#9DA6B2]/50 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-[#9DA6B2]">Neighborhoods</label>
              <input
                value={neighborhoods}
                onChange={(e) => setNeighborhoods(e.target.value)}
                placeholder="SoHo, East Village, Chelsea"
                className="w-full rounded-lg border border-[#2A3038] bg-[#121820] px-3 py-2.5 text-sm text-[#F7F4EF] placeholder-[#9DA6B2]/50 focus:border-orange-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-[#9DA6B2]">Ad inventory</label>
              <div className="space-y-2">
                {["window", "vehicle"].map((type) => (
                  <label key={type} className="flex items-center gap-2 rounded-lg border border-[#2A3038] bg-[#121820] px-3 py-2.5">
                    <input
                      type="checkbox"
                      checked={assetTypes.includes(type)}
                      onChange={(e) => {
                        if (e.target.checked) setAssetTypes([...assetTypes, type]);
                        else setAssetTypes(assetTypes.filter((t) => t !== type));
                      }}
                      className="h-4 w-4 accent-orange-500"
                    />
                    <span className="text-sm text-[#F7F4EF] capitalize">{type === "window" ? "First-floor windows" : "Rear car windows"}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-[#9DA6B2]">Budget</label>
                <div className="flex items-center gap-2 rounded-lg border border-[#2A3038] bg-[#121820] px-3">
                  <DollarSign className="h-4 w-4 text-[#D6A85C]" />
                  <input
                    type="number"
                    value={budget}
                    onChange={(e) => setBudget(Number(e.target.value))}
                    className="flex-1 bg-transparent py-2.5 text-sm text-[#F7F4EF] focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-[#9DA6B2]">Duration (days)</label>
                <div className="flex items-center gap-2 rounded-lg border border-[#2A3038] bg-[#121820] px-3">
                  <Calendar className="h-4 w-4 text-[#9DA6B2]" />
                  <input
                    type="number"
                    value={duration}
                    onChange={(e) => setDuration(Number(e.target.value))}
                    className="flex-1 bg-transparent py-2.5 text-sm text-[#F7F4EF] focus:outline-none"
                  />
                </div>
              </div>
            </div>

            <button
              onClick={handleCreate}
              disabled={!title || !city || loading}
              className="w-full rounded-xl bg-orange-500 py-3.5 text-sm font-bold uppercase tracking-wider text-zinc-950 hover:bg-orange-400 disabled:opacity-50 transition-colors"
            >
              {loading ? "Creating..." : "Create Campaign"}
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col items-center py-10 text-center">
            <Megaphone className="h-10 w-10 text-orange-400" />
            <p className="mt-3 text-sm font-semibold text-[#F7F4EF]">Campaign created</p>
            <p className="text-xs text-[#9DA6B2]">Fund to launch</p>
            <button
              onClick={handleFund}
              disabled={loading}
              className="mt-6 w-full rounded-xl bg-[#D6A85C] py-3.5 text-sm font-bold uppercase tracking-wider text-zinc-950 hover:bg-[#c49a50] disabled:opacity-50 transition-colors"
            >
              {loading ? "Processing..." : `Fund $${budget}`}
            </button>
          </div>
        )}

        {step === 3 && (
          <div className="flex flex-col items-center py-10 text-center">
            <CheckCircle className="h-10 w-10 text-[#27D17F]" />
            <p className="mt-3 text-sm font-semibold text-[#F7F4EF]">Campaign funded and live</p>
            <p className="text-xs text-[#9DA6B2]">Redirecting to dashboard...</p>
          </div>
        )}
      </main>
    </div>
  );
}
