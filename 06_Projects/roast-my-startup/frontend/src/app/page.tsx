"use client";

import { useState } from "react";
import { Flame } from "lucide-react";

export default function Home() {
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [intensity, setIntensity] = useState("spicy");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const response = await fetch("http://localhost:8000/api/roasts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          description,
          intensity,
          visibility: "public",
        }),
      });

      if (!response.ok) throw new Error("Failed to create roast");

      const data = await response.json();
      
      // Poll for job completion
      const pollInterval = setInterval(async () => {
        const statusResponse = await fetch(`http://localhost:8000/api/roasts/${data.job_id}`);
        const statusData = await statusResponse.json();

        if (statusData.status === "completed" && statusData.slug) {
          clearInterval(pollInterval);
          window.location.href = `/report/${statusData.slug}`;
        } else if (statusData.status === "failed") {
          clearInterval(pollInterval);
          alert("Roast failed: " + (statusData.error || "Unknown error"));
          setIsSubmitting(false);
        }
      }, 2000);
    } catch (error) {
      console.error("Error:", error);
      alert("Failed to submit URL. Please try again.");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background-primary">
      <nav className="border-b border-border px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flame className="w-8 h-8 text-orange-primary" />
            <span className="text-2xl font-bold text-text-main">Roast My Startup</span>
          </div>
          <div className="flex items-center gap-6 text-text-muted">
            <a href="#" className="hover:text-orange-primary transition-colors">Gallery</a>
            <a href="#" className="hover:text-orange-primary transition-colors">Leaderboard</a>
            <a href="#" className="hover:text-orange-primary transition-colors">Pricing</a>
            <button className="gradient-orange px-4 py-2 rounded-lg font-semibold text-background-primary hover:scale-105 transition-transform">
              Roast Yours
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center mb-16">
          <h1 className="text-6xl font-bold mb-6 text-text-main leading-tight">
            Your startup feedback is too polite.
          </h1>
          <p className="text-xl text-text-muted max-w-3xl mx-auto">
            Paste your URL and get roasted by a VC, a grumpy engineer, a savage customer, a designer, and a growth marketer. Funny enough to share. Useful enough to fix.
          </p>
        </div>

        <div className="max-w-2xl mx-auto glass-card rounded-2xl p-8 border-glow">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-text-muted mb-2">
                Startup URL
              </label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://yourstartup.com"
                className="w-full px-4 py-3 rounded-lg bg-background-tertiary border border-border text-text-main placeholder-text-muted focus:outline-none focus:border-orange-primary focus:ring-2 focus:ring-orange-primary/20 transition-all"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-text-muted mb-2">
                What are you building? (Optional)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of your startup..."
                rows={3}
                className="w-full px-4 py-3 rounded-lg bg-background-tertiary border border-border text-text-main placeholder-text-muted focus:outline-none focus:border-orange-primary focus:ring-2 focus:ring-orange-primary/20 transition-all resize-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-text-muted mb-2">
                Roast Intensity
              </label>
              <div className="flex gap-3">
                {["mild", "spicy", "savage"].map((level) => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setIntensity(level)}
                    className={`flex-1 px-4 py-2 rounded-lg font-medium capitalize transition-all ${
                      intensity === level
                        ? "gradient-orange text-background-primary"
                        : "bg-background-tertiary border border-border text-text-muted hover:border-orange-primary"
                    }`}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full gradient-orange px-6 py-4 rounded-lg font-bold text-background-primary text-lg hover:scale-[1.02] active:scale-[0.98] transition-transform shadow-glow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? "Roasting..." : "Roast My Startup"}
            </button>
          </form>
        </div>

        {/* Sample Roast Cards */}
        <div className="mt-20">
          <h2 className="text-2xl font-bold text-text-main mb-8 text-center">Recent Roasts</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { score: 42, quote: "Your homepage says AI-powered five times and customer pain zero times." },
              { score: 31, quote: "This looks like a Chrome extension wearing a Series A costume." },
              { score: 58, quote: "Not terrible. Just aggressively forgettable." },
            ].map((roast, i) => (
              <div key={i} className="glass-card rounded-xl p-6 border-glow hover:scale-105 transition-transform cursor-pointer">
                <div className="text-4xl font-bold text-orange-primary mb-3">{roast.score}/100</div>
                <p className="text-text-muted italic">"{roast.quote}"</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
