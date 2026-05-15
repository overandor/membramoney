"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { membraAPI } from "@/lib/api";
import { ArrowLeft, Shield, CheckCircle, XCircle, Loader2, QrCode } from "lucide-react";
import Link from "next/link";

export default function AccessPage() {
  const { visit } = useParams();
  const [visitData, setVisitData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!visit) return;
    membraAPI.getReservation(visit as string)
      .then(setVisitData)
      .finally(() => setLoading(false));
  }, [visit]);

  if (loading) {
    return (
      <div className="flex min-h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-400" />
      </div>
    );
  }

  const isReady = visitData?.status === "access_issued" || visitData?.status === "checked_in";
  const isDenied = visitData?.status === "risk_denied";

  return (
    <div className="flex min-h-full flex-col bg-zinc-950">
      <header className="sticky top-0 z-50 flex h-14 items-center gap-3 border-b border-zinc-800 bg-zinc-950/80 px-4 backdrop-blur-md">
        <Link href="/" className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900">
          <ArrowLeft className="h-4 w-4 text-zinc-400" />
        </Link>
        <h1 className="text-base font-bold">Your Access</h1>
      </header>

      <main className="flex flex-1 flex-col items-center px-4 py-8">
        {/* Status */}
        <div className="mb-6 flex items-center gap-2">
          {isReady ? (
            <>
              <Shield className="h-5 w-5 text-emerald-400" />
              <span className="text-sm font-semibold text-emerald-400">Insured Access Active</span>
            </>
          ) : isDenied ? (
            <>
              <XCircle className="h-5 w-5 text-red-400" />
              <span className="text-sm font-semibold text-red-400">Access Denied</span>
            </>
          ) : (
            <>
              <Loader2 className="h-5 w-5 animate-spin text-amber-400" />
              <span className="text-sm font-semibold text-amber-400">{visitData?.status}</span>
            </>
          )}
        </div>

        {/* QR Code placeholder */}
        {isReady && (
          <div className="mb-6 flex aspect-square w-64 items-center justify-center rounded-2xl border-2 border-dashed border-emerald-500/30 bg-zinc-900">
            <div className="text-center">
              <QrCode className="mx-auto h-16 w-16 text-emerald-400" />
              <p className="mt-2 text-xs text-zinc-500">Scan at entry point</p>
            </div>
          </div>
        )}

        {/* Visit details */}
        <div className="w-full max-w-sm rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <h3 className="mb-3 text-sm font-semibold text-zinc-300">Reservation Details</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-zinc-400">
              <span>Visit ID</span>
              <span className="text-zinc-200 font-mono text-xs">{visitData?.visit_id?.slice(0, 16)}...</span>
            </div>
            <div className="flex justify-between text-zinc-400">
              <span>Status</span>
              <span className="text-zinc-200">{visitData?.status}</span>
            </div>
            <div className="flex justify-between text-zinc-400">
              <span>Payment</span>
              <span className="text-emerald-400">{visitData?.payment_authorized ? "Authorized" : "Pending"}</span>
            </div>
            <div className="flex justify-between text-zinc-400">
              <span>Risk</span>
              <span className={visitData?.risk_score !== undefined ? "text-emerald-400" : "text-zinc-500"}>
                {visitData?.risk_score !== undefined ? `Score: ${visitData.risk_score}` : "Not scored"}
              </span>
            </div>
          </div>
        </div>

        {/* Gate check */}
        <div className="mt-6 w-full max-w-sm space-y-2">
          <GateCheck label="Identity Verified" passed={true} />
          <GateCheck label="Risk Approved" passed={visitData?.status !== "risk_denied"} />
          <GateCheck label="Payment Authorized" passed={visitData?.payment_authorized} />
          <GateCheck label="Coverage Active" passed={isReady} />
        </div>
      </main>
    </div>
  );
}

function GateCheck({ label, passed }: { label: string; passed: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-zinc-900/50 px-3 py-2">
      <span className="text-xs text-zinc-400">{label}</span>
      {passed ? (
        <CheckCircle className="h-4 w-4 text-emerald-400" />
      ) : (
        <XCircle className="h-4 w-4 text-red-400" />
      )}
    </div>
  );
}
