"use client";

import { useState } from "react";
import { Camera, MapPin, CheckCircle, ArrowLeft, Shield } from "lucide-react";
import Link from "next/link";
import { membraAPI } from "@/lib/api";

export default function AdsProofPage() {
  const [placementId, setPlacementId] = useState("");
  const [photoUrl, setPhotoUrl] = useState("");
  const [lat, setLat] = useState(40.7308);
  const [lng, setLng] = useState(-73.9975);
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [proofId, setProofId] = useState("");

  async function handleSubmit() {
    setLoading(true);
    try {
      const proof = await membraAPI.submitAdProof({
        placement_id: placementId || "plc_demo",
        proof_type: "photo",
        photo_url: photoUrl || "https://membra.demo/proof.jpg",
        latitude: lat,
        longitude: lng,
      });
      setProofId(proof.proof_id);
      setStep(2);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-full flex-col bg-[#080A0D]">
      <header className="sticky top-0 z-50 flex h-14 items-center gap-3 border-b border-[#2A3038] bg-[#080A0D]/80 px-4 backdrop-blur-md">
        <Link href="/ads/owner" className="flex h-8 w-8 items-center justify-center rounded-full bg-[#121820]">
          <ArrowLeft className="h-4 w-4 text-[#9DA6B2]" />
        </Link>
        <h1 className="text-base font-bold text-[#F7F4EF]">Verify Placement</h1>
      </header>

      <main className="flex-1 px-4 py-6">
        {step === 1 && (
          <div className="space-y-5">
            {/* Campaign info */}
            <div className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
              <p className="text-sm font-semibold text-[#F7F4EF]">Campaign</p>
              <p className="text-xs text-[#9DA6B2] mt-0.5">Joe's Pizza Grand Opening</p>
            </div>

            {/* Step 1: Photo */}
            <div className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-orange-500/10 text-xs font-bold text-orange-400">1</span>
                <p className="text-sm font-semibold text-[#F7F4EF]">Take photo of installed ad</p>
              </div>
              <button className="w-full rounded-lg border border-dashed border-[#2A3038] bg-[#080A0D] py-8 text-center hover:border-orange-500/50 transition-colors">
                <Camera className="mx-auto h-6 w-6 text-[#9DA6B2]" />
                <p className="mt-2 text-xs text-[#9DA6B2]">Open Camera</p>
              </button>
              <input
                value={photoUrl}
                onChange={(e) => setPhotoUrl(e.target.value)}
                placeholder="Or paste photo URL"
                className="mt-2 w-full rounded-lg border border-[#2A3038] bg-[#080A0D] px-3 py-2 text-xs text-[#F7F4EF] placeholder-[#9DA6B2]/50 focus:border-orange-500 focus:outline-none"
              />
            </div>

            {/* Step 2: Location */}
            <div className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-orange-500/10 text-xs font-bold text-orange-400">2</span>
                <p className="text-sm font-semibold text-[#F7F4EF]">Location check</p>
              </div>
              <div className="flex items-center gap-2 rounded-lg bg-[#080A0D] px-3 py-2">
                <MapPin className="h-4 w-4 text-[#27D17F]" />
                <span className="text-xs text-[#27D17F]">GPS matches approved area</span>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <input type="number" step="0.0001" value={lat} onChange={(e) => setLat(Number(e.target.value))} className="rounded-lg border border-[#2A3038] bg-[#080A0D] px-3 py-2 text-xs text-[#F7F4EF]" />
                <input type="number" step="0.0001" value={lng} onChange={(e) => setLng(Number(e.target.value))} className="rounded-lg border border-[#2A3038] bg-[#080A0D] px-3 py-2 text-xs text-[#F7F4EF]" />
              </div>
            </div>

            {/* Step 3: Visibility */}
            <div className="rounded-xl border border-[#2A3038] bg-[#121820] p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-orange-500/10 text-xs font-bold text-orange-400">3</span>
                <p className="text-sm font-semibold text-[#F7F4EF]">Visibility check</p>
              </div>
              <div className="space-y-2">
                {["Street-facing", "Ad readable", "Timestamp verified"].map((check) => (
                  <div key={check} className="flex items-center gap-2 text-xs text-[#27D17F]">
                    <CheckCircle className="h-3.5 w-3.5" />
                    {check}
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full rounded-xl bg-orange-500 py-3.5 text-sm font-bold uppercase tracking-wider text-zinc-950 hover:bg-orange-400 disabled:opacity-50 transition-colors"
            >
              {loading ? "Submitting..." : "Submit Proof"}
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col items-center py-10 text-center">
            <Shield className="h-10 w-10 text-[#27D17F]" />
            <p className="mt-3 text-sm font-semibold text-[#F7F4EF]">Proof approved</p>
            <p className="text-xs text-[#9DA6B2] mt-1">Today's payout unlocked</p>
            <div className="mt-4 rounded-xl border border-[#2A3038] bg-[#121820] px-6 py-3">
              <p className="text-2xl font-bold text-[#D6A85C]">$12</p>
              <p className="text-[10px] text-[#9DA6B2]">Daily payout</p>
            </div>
            <Link
              href="/ads/owner"
              className="mt-6 w-full rounded-xl border border-[#2A3038] bg-[#121820] py-3.5 text-sm font-bold text-[#F7F4EF] hover:bg-[#1a2028] transition-colors"
            >
              Back to Dashboard
            </Link>
          </div>
        )}
      </main>
    </div>
  );
}
