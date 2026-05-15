"use client";

import { useEffect, useState } from "react";
import { Flame, Share2, Download, Copy, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { RoastReport } from "@/types";

export default function ReportPage({ params }: { params: { slug: string } }) {
  const [report, setReport] = useState<RoastReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchReport() {
      try {
        const response = await fetch(`http://localhost:8000/api/reports/${params.slug}`);
        if (!response.ok) throw new Error("Report not found");
        const data = await response.json();
        setReport(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load report");
      } finally {
        setLoading(false);
      }
    }
    fetchReport();
  }, [params.slug]);

  if (loading) {
    return <div className="min-h-screen bg-background-primary flex items-center justify-center text-text-main">Loading...</div>;
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-background-primary flex items-center justify-center px-6">
        <div className="text-center">
          <p className="text-orange-warning text-xl mb-4">{error || "Report not found"}</p>
          <Link href="/" className="text-orange-primary hover:underline">Return home</Link>
        </div>
      </div>
    );
  }

  const getScoreColor = (score: number) => {
    if (score < 40) return "text-orange-warning";
    if (score < 60) return "text-orange-primary";
    if (score < 80) return "text-orange-hot";
    return "text-green-500";
  };

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
          <div className="flex gap-2">
            <button className="p-2 rounded-lg bg-background-tertiary border border-border text-text-muted hover:text-orange-primary transition-colors">
              <Share2 className="w-5 h-5" />
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-12">
        {/* Score Card */}
        <div className="glass-card rounded-2xl p-8 border-glow mb-8">
          <div className="text-center">
            <h2 className="text-sm font-medium text-text-muted mb-2">ROAST SCORE</h2>
            <div className={`text-7xl font-bold mb-4 ${getScoreColor(report.overall_score)}`}>
              {report.overall_score}/100
            </div>
            <p className="text-2xl text-text-main mb-4">{report.shareable_quote}</p>
            <p className="text-text-muted">{report.one_line_diagnosis}</p>
          </div>
        </div>

        {/* Executive Roast */}
        <div className="glass-card rounded-2xl p-8 mb-8">
          <h3 className="text-2xl font-bold text-text-main mb-4">Executive Roast</h3>
          <p className="text-text-muted text-lg leading-relaxed">{report.savage_summary}</p>
        </div>

        {/* Agent Tribunal */}
        <div className="mb-8">
          <h3 className="text-2xl font-bold text-text-main mb-6">Agent Tribunal</h3>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Object.entries(report.agents).map(([agent, data]) => (
              <div key={agent} className="glass-card rounded-xl p-6 border-glow">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-lg font-bold text-text-main capitalize">{agent}</h4>
                  <span className="text-orange-primary font-bold">{data.score}/100</span>
                </div>
                <p className="text-text-muted mb-4 italic">"{data.roast}"</p>
                <p className="text-text-sm text-orange-primary">Fix: {data.fix}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Score Breakdown */}
        <div className="glass-card rounded-2xl p-8 mb-8">
          <h3 className="text-2xl font-bold text-text-main mb-6">Score Breakdown</h3>
          <div className="space-y-4">
            {Object.entries(report.scores).map(([category, score]) => (
              <div key={category}>
                <div className="flex justify-between mb-2">
                  <span className="text-text-muted capitalize">{category}</span>
                  <span className="text-orange-primary font-bold">{score}/25</span>
                </div>
                <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                  <div
                    className="h-full gradient-orange"
                    style={{ width: `${(score / 25) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* AI Wrapper Risk */}
        <div className="glass-card rounded-2xl p-8 mb-8 border-2 border-orange-warning/30">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-2xl font-bold text-text-main">AI Wrapper Risk</h3>
            <span className="text-3xl font-bold text-orange-warning">{report.ai_wrapper_risk.score}%</span>
          </div>
          <p className="text-text-muted mb-6">{report.ai_wrapper_risk.verdict}</p>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-orange-warning font-bold mb-2">Risk Factors</h4>
              <ul className="space-y-1">
                {report.ai_wrapper_risk.risk_factors.map((factor, i) => (
                  <li key={i} className="text-text-muted text-sm">• {factor}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-orange-primary font-bold mb-2">How to Reduce Risk</h4>
              <ul className="space-y-1">
                {report.ai_wrapper_risk.risk_reduction_plan.map((step, i) => (
                  <li key={i} className="text-text-muted text-sm">• {step}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Rewrites */}
        <div className="glass-card rounded-2xl p-8 mb-8">
          <h3 className="text-2xl font-bold text-text-main mb-6">Landing Page Rewrite</h3>
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-text-muted mb-2">Hero Headline</label>
              <p className="text-text-main text-lg bg-background-tertiary p-4 rounded-lg">{report.rewrites.hero_headline}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-muted mb-2">Product Hunt Tagline</label>
              <p className="text-orange-primary text-lg bg-background-tertiary p-4 rounded-lg">{report.rewrites.product_hunt_tagline}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-muted mb-2">Primary CTA</label>
              <p className="text-text-main bg-background-tertiary p-4 rounded-lg">{report.rewrites.primary_cta}</p>
            </div>
          </div>
        </div>

        {/* Share Card */}
        <div className="glass-card rounded-2xl p-8 border-glow">
          <h3 className="text-2xl font-bold text-text-main mb-6">Share This Roast</h3>
          <div className="bg-background-tertiary rounded-xl p-8 border border-orange-primary/30 text-center">
            <h4 className="text-orange-primary font-bold mb-4">{report.share_card.headline}</h4>
            <div className="text-5xl font-bold text-orange-primary mb-4">{report.overall_score}/100</div>
            <p className="text-xl text-text-main mb-4 italic">"{report.share_card.quote}"</p>
            <div className="space-y-2 text-text-muted">
              <p><span className="text-orange-primary">Biggest issue:</span> {report.share_card.biggest_issue}</p>
              <p><span className="text-orange-primary">Fastest fix:</span> {report.share_card.fastest_fix}</p>
            </div>
            <p className="text-sm text-text-muted mt-6">roastmystartup.com</p>
          </div>
          <div className="flex gap-4 mt-6">
            <button className="flex-1 gradient-orange px-6 py-3 rounded-lg font-bold text-background-primary hover:scale-105 transition-transform flex items-center justify-center gap-2">
              <Download className="w-5 h-5" />
              Download PNG
            </button>
            <button className="flex-1 bg-background-tertiary border border-border px-6 py-3 rounded-lg font-bold text-text-main hover:border-orange-primary transition-colors flex items-center justify-center gap-2">
              <Copy className="w-5 h-5" />
              Copy Link
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
