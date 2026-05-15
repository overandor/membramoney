"use client";

import { useMembraStore } from "@/store/membra";
import { CATEGORY_LABELS } from "@/lib/types";
import { cn } from "@/lib/utils";

const CATEGORIES = Object.entries(CATEGORY_LABELS).map(([key, val]) => ({
  key,
  ...val,
}));

export function CategoryFilter() {
  const { selectedCategory, setSelectedCategory } = useMembraStore();

  return (
    <div className="sticky top-14 z-40 w-full border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-md">
      <div className="flex gap-2 overflow-x-auto px-4 py-3 scrollbar-hide">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.label}
            onClick={() => setSelectedCategory(cat.label)}
            className={cn(
              "flex shrink-0 items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm font-medium transition-all",
              selectedCategory === cat.label
                ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
                : "border-zinc-800 bg-zinc-900 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
            )}
          >
            <span className="text-base">{cat.icon}</span>
            <span>{cat.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
