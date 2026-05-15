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
  distanceMiles?: number;
  insurable?: boolean;
  verified?: boolean;
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
}

export interface MembraParty {
  party_id: string;
  name: string;
  email: string;
  identity_verified: boolean;
}

export type AssetCategory =
  | "All"
  | "restroom"
  | "printer"
  | "luggage_drop"
  | "shower"
  | "parking"
  | "ev_charger"
  | "storage_locker"
  | "laundry"
  | "coworking_desk";

export const CATEGORY_LABELS: Record<string, { label: string; icon: string }> = {
  All: { label: "All", icon: "🔍" },
  restroom: { label: "Restroom", icon: "🚻" },
  printer: { label: "Printer", icon: "🖨️" },
  luggage_drop: { label: "Luggage", icon: "🧳" },
  shower: { label: "Shower", icon: "�" },
  parking: { label: "Parking", icon: "🅿️" },
  ev_charger: { label: "EV Charger", icon: "�" },
  storage_locker: { label: "Storage", icon: "📦" },
  laundry: { label: "Laundry", icon: "🧺" },
  coworking_desk: { label: "Workspace", icon: "💼" },
};
