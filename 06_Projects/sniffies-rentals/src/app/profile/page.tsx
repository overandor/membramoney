"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft, Star, BadgeCheck, Settings, ListOrdered, Heart } from "lucide-react";

export default function ProfilePage() {
  const router = useRouter();

  const menuItems = [
    { icon: ListOrdered, label: "My Listings", count: 3 },
    { icon: Heart, label: "Saved Items", count: 12 },
    { icon: Star, label: "Reviews", count: 8 },
    { icon: Settings, label: "Settings" },
  ];

  return (
    <div className="flex min-h-full flex-col bg-zinc-950">
      <header className="sticky top-0 z-50 flex h-14 items-center gap-3 border-b border-zinc-800 bg-zinc-950/80 px-4 backdrop-blur-md">
        <button
          onClick={() => router.back()}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 hover:bg-zinc-800 transition-colors"
        >
          <ArrowLeft className="h-4 w-4 text-zinc-400" />
        </button>
        <h1 className="text-base font-bold">Profile</h1>
      </header>

      <main className="flex-1 px-4 py-6">
        {/* User card */}
        <div className="mb-6 flex items-center gap-4">
          <div className="relative">
            <img
              src="https://i.pravatar.cc/150?u=me"
              alt="You"
              className="h-16 w-16 rounded-full border-2 border-zinc-800 object-cover"
            />
            <div className="absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500">
              <BadgeCheck className="h-3 w-3 text-zinc-950" />
            </div>
          </div>
          <div>
            <h2 className="text-lg font-bold text-zinc-100">You</h2>
            <div className="mt-0.5 flex items-center gap-1 text-sm text-zinc-400">
              <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
              <span className="font-medium text-zinc-300">4.9</span>
              <span>(24 reviews)</span>
            </div>
            <p className="mt-0.5 text-xs text-zinc-500">Member since 2024</p>
          </div>
        </div>

        {/* Stats */}
        <div className="mb-6 grid grid-cols-3 gap-3">
          {[
            { label: "Listings", value: "3" },
            { label: "Rented", value: "47" },
            { label: "Earned", value: "$1.2k" },
          ].map((stat) => (
            <div
              key={stat.label}
              className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-3 text-center"
            >
              <p className="text-lg font-bold text-zinc-100">{stat.value}</p>
              <p className="text-xs text-zinc-500">{stat.label}</p>
            </div>
          ))}
        </div>

        {/* Menu */}
        <div className="space-y-2">
          {menuItems.map((item) => (
            <button
              key={item.label}
              className="flex w-full items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/50 px-4 py-3.5 text-left hover:bg-zinc-900 transition-colors"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-800">
                <item.icon className="h-4 w-4 text-zinc-400" />
              </div>
              <span className="flex-1 text-sm font-medium text-zinc-200">
                {item.label}
              </span>
              {"count" in item && (
                <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs font-semibold text-zinc-400">
                  {item.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </main>
    </div>
  );
}
