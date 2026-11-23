/** Mirrors `backend/app/api/v1/schemas/settings.py`. */

export type BandCaps = Record<"A" | "B" | "C" | "D" | "E", number>;
export type RegimeWeights = Record<"trend" | "vix" | "iv_rank", number>;

export interface UserSettings {
  notify_weekly_picks: boolean;
  notify_market_regime: boolean;
  default_symbol: string;
  theme: "light" | "dark" | "system";
  screener_preset: Record<string, unknown>;
  account_size: number;
  base_risk_pct: number;
  growth_risk_pct: number;
  min_equity: number;
  band_caps: BandCaps;
  regime_weights: RegimeWeights;
  widget_toggles: Record<string, boolean>;
  enforce_gate: boolean;
  /** Only the rule thresholds the user changed. */
  thresholds: Partial<Thresholds>;
  /** Every threshold with the user's changes applied. */
  effective_thresholds: Thresholds;
  disclaimer_accepted_at: string | null;
}

export interface Thresholds {
  spread_max_pct: number;
  open_interest_min: number;
  market_cap_min: number;
  earnings_window_days: number;
  correlation_max: number;
  /** 1 lets band D (speculative) trades through the gate; band E is always rejected. */
  allow_band_d: number;
  max_capital_at_risk_pct: number;
  max_sector_risk_pct: number;
  max_net_delta_pct: number;
  dte_watch: number;
  dte_warning: number;
  delta_assignment: number;
}

export interface ThresholdInfo {
  defaults: Thresholds;
  bounds: Record<keyof Thresholds, { min: number; max: number }>;
  overrides: Partial<Thresholds>;
  effective: Thresholds;
  /** Safety thresholds currently set looser than their default. */
  loosened: (keyof Thresholds)[];
}

export type SettingsUpdate = Partial<
  Omit<UserSettings, "disclaimer_accepted_at" | "effective_thresholds">
>;
