export interface RoastRequest {
  url: string;
  description?: string;
  intensity: "mild" | "spicy" | "savage";
  visibility: "public" | "private";
}

export interface RoastJob {
  id: string;
  url: string;
  status: "queued" | "processing" | "completed" | "failed";
  stage?: string;
  created_at: string;
  intensity?: string;
  visibility?: string;
  slug?: string;
  error?: string;
}

export interface AgentResponse {
  score: number;
  roast: string;
  fix: string;
}

export interface ScoreBreakdown {
  positioning: number;
  copy: number;
  conversion: number;
  pricing: number;
  trust: number;
  moat: number;
}

export interface AIWrapperRisk {
  score: number;
  verdict: string;
  risk_factors: string[];
  risk_reduction_plan: string[];
}

export interface Rewrites {
  hero_headline: string;
  subheadline: string;
  primary_cta: string;
  product_hunt_tagline: string;
  one_liner: string;
}

export interface ShareCard {
  headline: string;
  quote: string;
  biggest_issue: string;
  fastest_fix: string;
}

export interface RoastReport {
  startup_name: string;
  url: string;
  overall_score: number;
  score_label: string;
  savage_summary: string;
  one_line_diagnosis: string;
  shareable_quote: string;
  scores: ScoreBreakdown;
  agents: {
    vc: AgentResponse;
    customer: AgentResponse;
    engineer: AgentResponse;
    designer: AgentResponse;
    growth: AgentResponse;
  };
  ai_wrapper_risk: AIWrapperRisk;
  top_problems: Array<{
    priority: string;
    fix: string;
    why: string;
    difficulty: string;
  }>;
  quick_wins: Array<{
    fix: string;
    impact: string;
  }>;
  rewrites: Rewrites;
  share_card: ShareCard;
  slug: string;
  created_at: string;
}
