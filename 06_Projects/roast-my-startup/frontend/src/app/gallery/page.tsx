"use client";

import { useEffect, useState } from "react";
import { Flame, ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function GalleryPage() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchGallery() {
      try {
        const response = await fetch("http://localhost:8000/api/gallery");
        if (response.ok) {
          const data = await response.json();
          setReports(data);
        }
      } catch (error) {
        console.error("Failed to fetch gallery:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchGallery();
  }, []);

  return (
    <div className="min-h-screen bg-background-primary">
      <nav className="border-b border-border px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-text-muted hover:text-orange-primary transition-colors">
            <ArrowLeft className="w-5 h-5" />
            <span>Back</span>
          </Link>
          <div className="flex items-center gap-2">
            <Flame className="w-8 h-8 text-orange-primary" />
            <span className="text-2xl font-bold text-text-main">Roast My Startup</span>
          </div>
          <div />
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-12">
        <h1 className="text-4xl font-bold text-text-main mb-8">Public Roasts</h1>

        {loading ? (
          <p className="text-text-muted">Loading...</p>
        ) : reports.length === 0 ? (
          <div className="glass-card rounded-2xl p-12 text-center border-glow">
            <p className="text-text-muted text-lg">No public roasts yet. Be the first!</p>
            <Link href="/" className="inline-block mt-4 gradient-orange px-6 py-3 rounded-lg font-bold text-background-primary hover:scale-105 transition-transform">
              Roast Your Startup
            </Link>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {reports.map((report) => (
              <Link key={report.slug} href={`/report/${report.slug}`} className="glass-card rounded-xl p-6 border-glow hover:scale-105 transition-transform cursor-pointer">
                <div className="text-4xl font-bold text-orange-primary mb-3">{report.overall_score}/100</div>
                <h3 className="text-text-main font-bold mb-2">{report.startup_name}</h3>
                <p className="text-text-muted text-sm italic mb-4">"{report.shareable_quote}"</p>
                <p className="text-orange-primary text-sm">Read report →</p>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
