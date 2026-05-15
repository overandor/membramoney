"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { membraAPI } from "@/lib/api";
import { MembraAsset } from "@/lib/types";
import { ArrowLeft, Shield, Clock, CreditCard, CheckCircle, Loader2 } from "lucide-react";
import Link from "next/link";

export default function BookPage() {
  const { asset_id } = useParams();
  const router = useRouter();
  const [asset, setAsset] = useState<MembraAsset | null>(null);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);
  const [step, setStep] = useState(1);
  const [visit, setVisit] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!asset_id) return;
    membraAPI.getAsset(asset_id as string)
      .then(setAsset)
      .catch(() => setError("Asset not found"))
      .finally(() => setLoading(false));
  }, [asset_id]);

  async function handleBook() {
    setBooking(true);
    setError(null);
    try {
      // Step 1: Create reservation
      const start = new Date();
      const end = new Date(start.getTime() + 60 * 60 * 1000); // +1 hour
      const res = await membraAPI.createReservation({
        asset_id: asset_id as string,
        guest_id: "usr_3df41c7cf9a34c58",
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        guest_count: 1,
      });
      setVisit(res);
      setStep(2);

      // Step 2: Complete full flow (risk -> insurance -> payment -> QR)
      const complete = await membraAPI.completeFlow(res.visit_id);
      setVisit(complete);
      setStep(3);

      // Redirect to access page with QR
      if (complete.qr_token) {
        setTimeout(() => {
          router.push(`/access/${complete.visit_id}`);
        }, 1500);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBooking(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-400" />
      </div>
    );
  }

  if (error && !asset) {
    return (
      <div className="flex min-h-full flex-col items-center justify-center px-4 text-center">
        <p className="text-red-400">{error}</p>
        <Link href="/" className="mt-4 text-emerald-400">Back to map</Link>
      </div>
    );
  }

  const price = asset ? (asset.price_cents / 100).toFixed(2) : "0.00";

  return (
    <div className="flex min-h-full flex-col bg-zinc-950">
      <header className="sticky top-0 z-50 flex h-14 items-center gap-3 border-b border-zinc-800 bg-zinc-950/80 px-4 backdrop-blur-md">
        <Link href="/" className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900">
          <ArrowLeft className="h-4 w-4 text-zinc-400" />
        </Link>
        <h1 className="text-base font-bold">Book Access</h1>
      </header>

      <main className="flex-1 px-4 py-6">
        {/* Progress */}
        <div className="mb-6 flex gap-2">
          {[1, 2, 3].map((s) => (
            <div key={s} className={`h-1.5 flex-1 rounded-full ${s <= step ? "bg-emerald-500" : "bg-zinc-800"}`} />
          ))}
        </div>

        {asset && (
          <div className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
            <h2 className="text-lg font-bold text-zinc-100">{asset.title}</h2>
            <p className="mt-1 text-sm text-zinc-400">{asset.description}</p>
            <div className="mt-3 flex items-center gap-2">
              <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-sm font-semibold text-emerald-400">
                ${price}
              </span>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <h3 className="mb-3 text-sm font-semibold text-zinc-300">What you get</h3>
              <div className="space-y-2">
                {[
                  { icon: Shield, text: "Identity-verified access" },
                  { icon: Clock, text: "1-hour time-bounded window" },
                  { icon: CreditCard, text: "Payment-backed reservation" },
                  { icon: CheckCircle, text: "Insurance-covered visit" },
                ].map((item) => (
                  <div key={item.text} className="flex items-center gap-2 text-sm text-zinc-400">
                    <item.icon className="h-4 w-4 text-emerald-400" />
                    {item.text}
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={handleBook}
              disabled={booking}
              className="w-full rounded-xl bg-emerald-500 py-3.5 text-sm font-bold uppercase tracking-wider text-zinc-950 hover:bg-emerald-400 disabled:opacity-50 transition-colors"
            >
              {booking ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Processing...
                </span>
              ) : (
                "Authorize & Book"
              )}
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col items-center py-10 text-center">
            <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
            <p className="mt-3 text-sm text-zinc-400">Running risk check...</p>
            <p className="text-xs text-zinc-600">Insurance quote & payment authorization</p>
          </div>
        )}

        {step === 3 && (
          <div className="flex flex-col items-center py-10 text-center">
            <CheckCircle className="h-10 w-10 text-emerald-400" />
            <p className="mt-3 text-sm font-semibold text-zinc-200">Access granted</p>
            <p className="text-xs text-zinc-500">Redirecting to your QR code...</p>
          </div>
        )}

        {error && step < 3 && (
          <div className="mt-4 rounded-xl border border-red-800 bg-red-900/20 p-3 text-sm text-red-300">
            {error}
          </div>
        )}
      </main>
    </div>
  );
}
