"use client";

import { Shield, ScanLine, User, LayoutGrid, Megaphone } from "lucide-react";
import Link from "next/link";
import { useMembraStore } from "@/store/membra";
import { usePathname } from "next/navigation";

export function Navbar() {
  const { appMode, setAppMode } = useMembraStore();
  const pathname = usePathname();
  const isAds = pathname.startsWith("/ads") || appMode === "ads";

  return (
    <header className="sticky top-0 z-50 w-full border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md">
      <div className="flex h-14 items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2">
            <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${isAds ? "bg-orange-500" : "bg-emerald-500"}`}>
              <Shield className="h-5 w-5 text-zinc-950" />
            </div>
            <span className="text-lg font-bold tracking-tight">Membra</span>
          </Link>

          {/* Mode Switch */}
          <div className="ml-2 flex rounded-lg border border-zinc-800 bg-zinc-900/50 p-0.5">
            <Link
              href="/"
              onClick={() => setAppMode("access")}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${!isAds ? "bg-emerald-500/10 text-emerald-400" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              Access
            </Link>
            <Link
              href="/ads"
              onClick={() => setAppMode("ads")}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${isAds ? "bg-orange-500/10 text-orange-400" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              <Megaphone className="h-3.5 w-3.5" />
              Ads
            </Link>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {!isAds && (
            <Link
              href="/scan"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-900 hover:bg-zinc-800 transition-colors"
            >
              <ScanLine className="h-4 w-4 text-zinc-400" />
            </Link>
          )}
          <Link
            href={isAds ? "/ads/owner" : "/profile"}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-900 hover:bg-zinc-800 transition-colors"
          >
            <User className="h-4 w-4 text-zinc-400" />
          </Link>
        </div>
      </div>
    </header>
  );
}
