"use client";

import { useEffect, useState } from "react";
import { Flame, Skull, Zap } from "lucide-react";

const stages = [
  "VC Agent is checking if this is fundable...",
  "Customer Agent is trying to understand why they should care...",
  "Engineer Agent is looking for duct tape in the architecture...",
  "Designer Agent is judging your visual hierarchy...",
  "Growth Agent is searching for a repeatable hook...",
  "Savage Agent is preheating the oven...",
  "Counting how many times you said 'AI-powered'...",
  "Looking for a target customer. Still looking...",
  "Checking if your CTA has a pulse...",
  "Asking the pricing page why it is hiding...",
  "Preparing emotional damage...",
];

export default function LoadingTribunal() {
  const [currentStage, setCurrentStage] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) return 100;
        return prev + 2;
      });
    }, 100);

    const stageInterval = setInterval(() => {
      setCurrentStage((prev) => (prev + 1) % stages.length);
    }, 1500);

    return () => {
      clearInterval(interval);
      clearInterval(stageInterval);
    };
  }, []);

  return (
    <div className="min-h-screen bg-background-primary flex items-center justify-center px-6">
      <div className="max-w-2xl w-full">
        <div className="text-center mb-12">
          <div className="flex justify-center mb-6">
            <Flame className="w-16 h-16 text-orange-primary animate-pulse" />
          </div>
          <h1 className="text-4xl font-bold text-text-main mb-4">AI Tribunal</h1>
          <p className="text-text-muted text-lg">The agents are judging your startup...</p>
        </div>

        <div className="glass-card rounded-2xl p-8 border-glow">
          <div className="mb-8">
            <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
              <div
                className="h-full gradient-orange transition-all duration-100 ease-linear"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="mt-2 text-right text-orange-primary font-mono text-sm">
              {progress}%
            </div>
          </div>

          <div className="space-y-4">
            {stages.slice(0, 5).map((stage, index) => (
              <div
                key={index}
                className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
                  index === currentStage
                    ? "bg-orange-primary/10 border border-orange-primary/30"
                    : index < currentStage
                    ? "bg-background-tertiary opacity-50"
                    : "bg-background-tertiary opacity-30"
                }`}
              >
                {index < currentStage ? (
                  <Zap className="w-5 h-5 text-orange-primary" />
                ) : index === currentStage ? (
                  <Flame className="w-5 h-5 text-orange-primary animate-pulse" />
                ) : (
                  <Skull className="w-5 h-5 text-text-muted" />
                )}
                <span className={index === currentStage ? "text-orange-primary" : "text-text-muted"}>
                  {stage}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
