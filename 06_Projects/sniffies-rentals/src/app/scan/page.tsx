"use client";

import { useState } from "react";
import { membraAPI } from "@/lib/api";
import { ArrowLeft, ScanLine, Shield, XCircle, CheckCircle, Loader2 } from "lucide-react";
import Link from "next/link";

export default function ScanPage() {
  const [qrInput, setQrInput] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [result, setResult] = useState<any>(null);

  async function handleVerify() {
    if (!qrInput.trim()) return;
    setVerifying(true);
    setResult(null);
    try {
      const res = await membraAPI.verifyQR(qrInput.trim());
      setResult(res);
    } catch (e: any) {
      setResult({ access_allowed: false, reason: e.message });
    } finally {
      setVerifying(false);
    }
  }

  async function handleCheckIn() {
    if (!result?.visit_id) return;
    try {
      const res = await membraAPI.checkIn(result.visit_id);
      setResult({ ...result, checked_in: true, status: res.status });
    } catch (e: any) {
      setResult({ ...result, error: e.message });
    }
  }

  return (
    <div className="flex min-h-full flex-col bg-zinc-950">
      <header className="sticky top-0 z-50 flex h-14 items-center gap-3 border-b border-zinc-800 bg-zinc-950/80 px-4 backdrop-blur-md">
        <Link href="/" className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900">
          <ArrowLeft className="h-4 w-4 text-zinc-400" />
        </Link>
        <h1 className="text-base font-bold">Scan QR Access</h1>
      </header>

      <main className="flex flex-1 flex-col items-center px-4 py-8">
        {/* Scanner icon */}
        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl border-2 border-dashed border-zinc-700 bg-zinc-900">
          <ScanLine className="h-8 w-8 text-zinc-500" />
        </div>

        {/* Input */}
        <div className="w-full max-w-sm space-y-3">
          <textarea
            value={qrInput}
            onChange={(e) => setQrInput(e.target.value)}
            placeholder="Paste QR payload here..."
            rows={4}
            className="w-full resize-none rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-xs font-mono text-zinc-100 placeholder-zinc-600 outline-none focus:border-emerald-500/50"
          />
          <button
            onClick={handleVerify}
            disabled={verifying || !qrInput.trim()}
            className="w-full rounded-xl bg-emerald-500 py-3 text-sm font-bold uppercase tracking-wider text-zinc-950 hover:bg-emerald-400 disabled:opacity-50 transition-colors"
          >
            {verifying ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Verifying...
              </span>
            ) : (
              "Verify Access"
            )}
          </button>
        </div>

        {/* Result */}
        {result && (
          <div className={`mt-6 w-full max-w-sm rounded-xl border p-4 ${
            result.access_allowed
              ? "border-emerald-800 bg-emerald-900/20"
              : "border-red-800 bg-red-900/20"
          }`}>
            <div className="flex items-center gap-2 mb-2">
              {result.access_allowed ? (
                <>
                  <Shield className="h-5 w-5 text-emerald-400" />
                  <span className="font-bold text-emerald-400">Access Allowed</span>
                </>
              ) : (
                <>
                  <XCircle className="h-5 w-5 text-red-400" />
                  <span className="font-bold text-red-400">Access Denied</span>
                </>
              )}
            </div>
            <p className="text-sm text-zinc-400">{result.reason}</p>
            {result.visit_id && (
              <p className="mt-1 text-xs text-zinc-500 font-mono">Visit: {result.visit_id}</p>
            )}
            {result.access_allowed && (
              <button
                onClick={handleCheckIn}
                className="mt-3 w-full rounded-lg bg-emerald-500 py-2 text-sm font-bold text-zinc-950 hover:bg-emerald-400 transition-colors"
              >
                Check In
              </button>
            )}
          </div>
        )}

        {/* Check-in success */}
        {result?.checked_in && (
          <div className="mt-3 w-full max-w-sm rounded-xl border border-emerald-800 bg-emerald-900/20 p-4 text-center">
            <CheckCircle className="mx-auto h-6 w-6 text-emerald-400" />
            <p className="mt-1 text-sm font-semibold text-emerald-400">Guest Checked In</p>
            <p className="text-xs text-zinc-500">Status: {result.status}</p>
          </div>
        )}
      </main>
    </div>
  );
}
