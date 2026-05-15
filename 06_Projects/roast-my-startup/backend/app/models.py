from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime

class RoastRequest(BaseModel):
    url: HttpUrl
    description: Optional[str] = ""
    intensity: str = "spicy"
    visibility: str = "public"

class RoastJob(BaseModel):
    id: str
    url: str
    status: str
    stage: Optional[str] = None
    created_at: datetime

class AgentResponse(BaseModel):
    agent: str
    score: int
    max_score: int
    roast: str
    evidence: List[str]
    fix: str
    rewrite: Optional[str] = None

class ScoreBreakdown(BaseModel):
    positioning: int
    copy: int
    conversion: int
    pricing: int
    trust: int
    moat: int

class AIWrapperRisk(BaseModel):
    score: int
    verdict: str
    risk_factors: List[str]
    risk_reduction_plan: List[str]

class Rewrites(BaseModel):
    hero_headline: str
    subheadline: str
    primary_cta: str
    product_hunt_tagline: str
    one_liner: str

class ShareCard(BaseModel):
    headline: str
    quote: str
    biggest_issue: str
    fastest_fix: str

class RoastReport(BaseModel):
    startup_name: str
    url: str
    overall_score: int
    score_label: str
    savage_summary: str
    one_line_diagnosis: str
    shareable_quote: str
    scores: ScoreBreakdown
    agents: Dict[str, Dict[str, Any]]
    ai_wrapper_risk: AIWrapperRisk
    top_problems: List[Dict[str, Any]]
    quick_wins: List[Dict[str, Any]]
    rewrites: Rewrites
    share_card: ShareCard
