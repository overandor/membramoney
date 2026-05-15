const API = process.env.NEXT_PUBLIC_MEMBRA_API_URL || "http://localhost:8000";

export interface MembraAsset {
  asset_id: string;
  category: string;
  title: string;
  description: string | null;
  rules: Record<string, any>;
  trust_badges: string[];
  price_cents: number;
  host_id?: string;
  latitude?: number;
  longitude?: number;
}

export interface MembraVisit {
  visit_id: string;
  asset_id: string;
  host_id: string;
  guest_id: string;
  status: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  payment_authorized: boolean;
  risk_score?: number;
  risk_reasons?: string[];
  qr_token?: string;
}

export interface MembraCoverage {
  coverage_id: string;
  visit_id: string;
  status: string;
  external_policy_id?: string;
  premium_cents?: number;
  coverage_limit_cents: number;
  deductible_cents: number;
  coverage_start?: string;
  coverage_end?: string;
}

export interface MembraParty {
  party_id: string;
  name: string;
  email: string;
  identity_verified: boolean;
}

export interface PaymentQuote {
  amount_cents: number;
  platform_fee_cents: number;
  insurance_premium_cents: number;
  host_payout_cents: number;
}

async function fetchJSON(path: string, opts?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export const membraAPI = {
  // Auth
  register: (data: { email: string; name: string; party_type?: string }) =>
    fetchJSON("/public/v1/register", { method: "POST", body: JSON.stringify(data) }),
  login: (data: { email: string }) =>
    fetchJSON("/public/v1/login", { method: "POST", body: JSON.stringify(data) }),

  // Assets
  listAssets: (): Promise<MembraAsset[]> =>
    fetchJSON("/v1/assets"),
  getAsset: (id: string): Promise<MembraAsset> =>
    fetchJSON(`/v1/assets/${id}`),
  createAsset: (data: any) =>
    fetchJSON("/v1/assets", { method: "POST", body: JSON.stringify(data) }),

  // Reservations / Visits
  createReservation: (data: { asset_id: string; guest_id: string; start_time: string; end_time: string; guest_count?: number }) =>
    fetchJSON("/v1/reservations", { method: "POST", body: JSON.stringify(data) }),
  getReservation: (id: string): Promise<MembraVisit> =>
    fetchJSON(`/v1/reservations/${id}`),
  completeFlow: (visitId: string) =>
    fetchJSON(`/v1/reservations/${visitId}/approve`, { method: "POST" }),

  // Access
  getQR: (visitId: string) =>
    fetchJSON(`/v1/access/${visitId}/qr`, { method: "POST" }),
  verifyQR: (qrPayload: string) =>
    fetchJSON("/v1/access/verify", { method: "POST", body: JSON.stringify({ qr_payload: qrPayload }) }),
  checkIn: (visitId: string) =>
    fetchJSON("/v1/access/check-in", { method: "POST", body: JSON.stringify({ visit_id: visitId }) }),
  checkOut: (visitId: string) =>
    fetchJSON("/v1/access/check-out", { method: "POST", body: JSON.stringify({ visit_id: visitId }) }),

  // Payments
  createPayment: (data: { visit_id: string; amount_cents: number }) =>
    fetchJSON("/v1/payments/authorize", { method: "POST", body: JSON.stringify({ visit_id: data.visit_id }) }),

  // Ads: Campaigns
  listAdCampaigns: (status?: string): Promise<any[]> =>
    fetchJSON(status ? `/v1/ad-campaigns?status=${status}` : "/v1/ad-campaigns"),
  createAdCampaign: (data: any) =>
    fetchJSON("/v1/ad-campaigns", { method: "POST", body: JSON.stringify(data) }),
  getAdCampaign: (id: string) =>
    fetchJSON(`/v1/ad-campaigns/${id}`),
  submitCreative: (campaignId: string, data: any) =>
    fetchJSON(`/v1/ad-campaigns/${campaignId}/submit-creative`, { method: "POST", body: JSON.stringify(data) }),
  approveCreative: (campaignId: string) =>
    fetchJSON(`/v1/ad-campaigns/${campaignId}/approve-creative`, { method: "POST" }),
  fundCampaign: (campaignId: string) =>
    fetchJSON(`/v1/ad-campaigns/${campaignId}/fund`, { method: "POST" }),
  launchCampaign: (campaignId: string) =>
    fetchJSON(`/v1/ad-campaigns/${campaignId}/launch`, { method: "POST" }),

  // Ads: Placements
  acceptPlacement: (campaignId: string, data: { asset_id: string; owner_id: string; daily_rate_cents: number }) =>
    fetchJSON(`/v1/ad-campaigns/${campaignId}/accept`, { method: "POST", body: JSON.stringify(data) }),
  listPlacements: (params?: { campaign_id?: string; owner_id?: string }) =>
    fetchJSON("/v1/ad-placements" + (params ? "?" + new URLSearchParams(params as any).toString() : "")),
  generateQR: (placementId: string) =>
    fetchJSON(`/v1/ad-placements/${placementId}/qr`, { method: "POST" }),

  // Ads: Proofs
  submitAdProof: (data: { placement_id: string; proof_type: string; photo_url?: string; latitude?: number; longitude?: number }) =>
    fetchJSON("/v1/ad-proofs", { method: "POST", body: JSON.stringify(data) }),
  reviewProof: (placementId: string, verified: boolean = true) =>
    fetchJSON(`/v1/ad-proofs/${placementId}/review`, { method: "POST", body: JSON.stringify({ verified }) }),

  // Ads: Payouts
  createPayout: (data: { owner_id: string; placement_id: string; campaign_id: string; amount_cents: number }) =>
    fetchJSON("/v1/ad-payouts", { method: "POST", body: JSON.stringify(data) }),
  releasePayout: (payoutId: string) =>
    fetchJSON(`/v1/ad-payouts/${payoutId}/release`, { method: "POST" }),

  // Ads: Analytics
  getAdCampaignAnalytics: (campaignId: string) =>
    fetchJSON(`/v1/ad-analytics/campaign/${campaignId}`),
  getAdOwnerAnalytics: (ownerId: string) =>
    fetchJSON(`/v1/ad-analytics/owner/${ownerId}`),

  // Wear
  createWearer: (data: any) =>
    fetchJSON("/v1/wearers", { method: "POST", body: JSON.stringify(data) }),
  getWearer: (id: string) =>
    fetchJSON(`/v1/wearers/${id}`),
  listWearers: (city?: string) =>
    fetchJSON(city ? `/v1/wearers?city=${city}` : "/v1/wearers"),
  verifyWearer: (id: string) =>
    fetchJSON(`/v1/wearers/${id}/verify`, { method: "POST" }),
  createWearable: (data: any) =>
    fetchJSON("/v1/wearables", { method: "POST", body: JSON.stringify(data) }),
  listWearables: (params?: { wearer_id?: string; status?: string }) =>
    fetchJSON("/v1/wearables" + (params ? "?" + new URLSearchParams(params as any).toString() : "")),
  submitWearProof: (data: { placement_id: string; selfie_url: string; latitude?: number; longitude?: number }) =>
    fetchJSON("/v1/wear-proofs", { method: "POST", body: JSON.stringify(data) }),
  getWearCampaignAnalytics: (campaignId: string) =>
    fetchJSON(`/v1/wear-analytics/campaign/${campaignId}`),
  getWearerAnalytics: (wearerId: string) =>
    fetchJSON(`/v1/wear-analytics/wearer/${wearerId}`),

  // Health
  health: () => fetchJSON("/v1/health"),
};
