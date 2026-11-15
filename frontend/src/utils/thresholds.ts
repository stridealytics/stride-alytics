/** Rule-threshold form model: which values changed, and whether they are in range. */

import type { ThresholdInfo, Thresholds } from "../types";

export interface ThresholdField {
  key: keyof Thresholds;
  label: string;
  unit: string;
  group: "Do-Not-Trade gate" | "Portfolio limits" | "Exit alerts";
  hint: string;
}

export const THRESHOLD_FIELDS: ThresholdField[] = [
  {
    key: "spread_max_pct",
    label: "Widest bid/ask spread",
    unit: "%",
    group: "Do-Not-Trade gate",
    hint: "Blocks trades on wider spreads (BR-017).",
  },
  {
    key: "open_interest_min",
    label: "Minimum open interest",
    unit: "contracts",
    group: "Do-Not-Trade gate",
    hint: "Blocks illiquid contracts (BR-018).",
  },
  {
    key: "market_cap_min",
    label: "Minimum market cap",
    unit: "$",
    group: "Do-Not-Trade gate",
    hint: "Blocks small companies (BR-019).",
  },
  {
    key: "earnings_window_days",
    label: "Earnings blackout",
    unit: "days",
    group: "Do-Not-Trade gate",
    hint: "Blocks entries this close to earnings (BR-020).",
  },
  {
    key: "max_capital_at_risk_pct",
    label: "Capital at risk limit",
    unit: "% of equity",
    group: "Portfolio limits",
    hint: "Blocks new entries above this (BR-081).",
  },
  {
    key: "max_sector_risk_pct",
    label: "Sector exposure limit",
    unit: "% of equity",
    group: "Portfolio limits",
    hint: "Reported, does not block (BR-080).",
  },
  {
    key: "max_net_delta_pct",
    label: "Net delta limit",
    unit: "% of equity",
    group: "Portfolio limits",
    hint: "Reported, does not block (BR-080).",
  },
  {
    key: "dte_watch",
    label: "Watch at days to expiry",
    unit: "days",
    group: "Exit alerts",
    hint: "Raises a Watch alert (BR-050).",
  },
  {
    key: "dte_warning",
    label: "Warning at days to expiry",
    unit: "days",
    group: "Exit alerts",
    hint: "Raises a Warning alert; must be below the Watch value (BR-050).",
  },
  {
    key: "delta_assignment",
    label: "Assignment alarm delta",
    unit: "|delta|",
    group: "Exit alerts",
    hint: "Short option at or above this delta is an assignment alarm (BR-052).",
  },
];

export type ThresholdForm = Record<keyof Thresholds, string>;

export function toThresholdForm(effective: Thresholds): ThresholdForm {
  return Object.fromEntries(
    THRESHOLD_FIELDS.map((f) => [f.key, String(effective[f.key])]),
  ) as ThresholdForm;
}

/** Returns an error message, or null when every value is a number inside its allowed range. */
export function validateThresholds(
  form: ThresholdForm,
  info: ThresholdInfo,
): string | null {
  for (const f of THRESHOLD_FIELDS) {
    const raw = form[f.key].trim();
    const value = Number(raw);
    const { min, max } = info.bounds[f.key];
    if (raw === "" || !Number.isFinite(value))
      return `${f.label} must be a number.`;
    if (value < min || value > max)
      return `${f.label} must be between ${min} and ${max}.`;
  }
  if (Number(form.dte_warning) >= Number(form.dte_watch)) {
    return "The Warning days must be below the Watch days.";
  }
  return null;
}

/** Only the values that differ from the defaults (the server stores nothing else). */
export function toOverrides(
  form: ThresholdForm,
  defaults: Thresholds,
): Partial<Thresholds> {
  const out: Partial<Thresholds> = {};
  for (const f of THRESHOLD_FIELDS) {
    const value = Number(form[f.key]);
    if (value !== defaults[f.key]) out[f.key] = value;
  }
  return out;
}
