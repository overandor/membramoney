"use client";

import { useState } from "react";
import { ArrowLeft, Camera, MapPin, Tag, DollarSign, FileText } from "lucide-react";
import { useRouter } from "next/navigation";

export default function ListItemPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    title: "",
    category: "",
    priceHour: "",
    priceDay: "",
    description: "",
  });

  const categories = [
    "Tools",
    "Electronics",
    "Vehicles",
    "Camping",
    "Party",
    "Sports",
    "Clothing",
    "Furniture",
  ];

  const update = (key: string, value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <div className="flex min-h-full flex-col bg-zinc-950">
      {/* Header */}
      <header className="sticky top-0 z-50 flex h-14 items-center gap-3 border-b border-zinc-800 bg-zinc-950/80 px-4 backdrop-blur-md">
        <button
          onClick={() => router.back()}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 hover:bg-zinc-800 transition-colors"
        >
          <ArrowLeft className="h-4 w-4 text-zinc-400" />
        </button>
        <h1 className="text-base font-bold">List Your Item</h1>
      </header>

      <main className="flex-1 px-4 py-6">
        {/* Progress */}
        <div className="mb-6 flex gap-2">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={`h-1.5 flex-1 rounded-full transition-colors ${
                s <= step ? "bg-emerald-500" : "bg-zinc-800"
              }`}
            />
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-5">
            {/* Photo upload placeholder */}
            <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-zinc-800 bg-zinc-900/50 py-10">
              <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-zinc-800">
                <Camera className="h-6 w-6 text-zinc-500" />
              </div>
              <p className="text-sm font-medium text-zinc-300">Add Photos</p>
              <p className="mt-1 text-xs text-zinc-500">
                Tap to upload up to 5 images
              </p>
            </div>

            {/* Title */}
            <div>
              <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-zinc-300">
                <Tag className="h-3.5 w-3.5 text-zinc-500" />
                Title
              </label>
              <input
                type="text"
                value={form.title}
                onChange={(e) => update("title", e.target.value)}
                placeholder="e.g. DeWalt Power Drill Set"
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-emerald-500/50 transition-colors"
              />
            </div>

            {/* Category */}
            <div>
              <label className="mb-1.5 text-sm font-medium text-zinc-300">
                Category
              </label>
              <div className="flex flex-wrap gap-2">
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => update("category", cat)}
                    className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition-all ${
                      form.category === cat
                        ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
                        : "border-zinc-800 bg-zinc-900 text-zinc-400 hover:border-zinc-700"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            {/* Price */}
            <div>
              <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-zinc-300">
                <DollarSign className="h-3.5 w-3.5 text-zinc-500" />
                Price per Hour
              </label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm text-zinc-500">
                  $
                </span>
                <input
                  type="number"
                  value={form.priceHour}
                  onChange={(e) => update("priceHour", e.target.value)}
                  placeholder="8"
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-900 py-3 pl-8 pr-4 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-emerald-500/50 transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-zinc-300">
                <DollarSign className="h-3.5 w-3.5 text-zinc-500" />
                Price per Day
              </label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm text-zinc-500">
                  $
                </span>
                <input
                  type="number"
                  value={form.priceDay}
                  onChange={(e) => update("priceDay", e.target.value)}
                  placeholder="35"
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-900 py-3 pl-8 pr-4 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-emerald-500/50 transition-colors"
                />
              </div>
            </div>

            {/* Location hint */}
            <div className="flex items-start gap-3 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              <div>
                <p className="text-sm font-medium text-zinc-300">
                  Location set automatically
                </p>
                <p className="text-xs text-zinc-500">
                  We use your current location to show your item on the map.
                </p>
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-5">
            <div>
              <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-zinc-300">
                <FileText className="h-3.5 w-3.5 text-zinc-500" />
                Description
              </label>
              <textarea
                value={form.description}
                onChange={(e) => update("description", e.target.value)}
                placeholder="Describe your item, condition, and any rules..."
                rows={5}
                className="w-full resize-none rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-emerald-500/50 transition-colors"
              />
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-sm font-medium text-zinc-300">Preview</p>
              <div className="mt-2 text-xs text-zinc-500 space-y-1">
                <p>
                  <span className="text-zinc-400">Title:</span>{" "}
                  {form.title || "—"}
                </p>
                <p>
                  <span className="text-zinc-400">Category:</span>{" "}
                  {form.category || "—"}
                </p>
                <p>
                  <span className="text-zinc-400">Hourly:</span> ${form.priceHour || "—"}
                </p>
                <p>
                  <span className="text-zinc-400">Daily:</span> ${form.priceDay || "—"}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="mt-8 flex gap-3">
          {step > 1 && (
            <button
              onClick={() => setStep(step - 1)}
              className="flex-1 rounded-xl border border-zinc-800 py-3.5 text-sm font-semibold text-zinc-300 hover:bg-zinc-900 transition-colors"
            >
              Back
            </button>
          )}
          {step < 3 ? (
            <button
              onClick={() => setStep(step + 1)}
              className="flex-1 rounded-xl bg-emerald-500 py-3.5 text-sm font-bold uppercase tracking-wider text-zinc-950 hover:bg-emerald-400 transition-colors"
            >
              Continue
            </button>
          ) : (
            <button
              onClick={() => router.push("/")}
              className="flex-1 rounded-xl bg-emerald-500 py-3.5 text-sm font-bold uppercase tracking-wider text-zinc-950 hover:bg-emerald-400 transition-colors"
            >
              Publish Listing
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
