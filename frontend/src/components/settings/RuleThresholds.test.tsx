import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithClient } from "../../test/utils";
import type { ThresholdInfo, Thresholds } from "../../types";
import {
  toOverrides,
  toThresholdForm,
  validateThresholds,
} from "../../utils/thresholds";
import { RuleThresholds } from "./RuleThresholds";

vi.mock("../../api/endpoints", () => ({
  settingsApi: { thresholdInfo: vi.fn(), update: vi.fn() },
}));

import { settingsApi } from "../../api/endpoints";

const defaults: Thresholds = {
  spread_max_pct: 10,
  open_interest_min: 500,
  market_cap_min: 2_000_000_000,
  earnings_window_days: 14,
  correlation_max: 0.85,
  allow_band_d: 0,
  max_capital_at_risk_pct: 50,
  max_sector_risk_pct: 25,
  max_net_delta_pct: 100,
  dte_watch: 7,
  dte_warning: 3,
  delta_assignment: 0.7,
};

const bounds = {
  spread_max_pct: { min: 1, max: 25 },
  open_interest_min: { min: 0, max: 5000 },
  market_cap_min: { min: 0, max: 50_000_000_000 },
  earnings_window_days: { min: 0, max: 60 },
  correlation_max: { min: 0.5, max: 0.99 },
  allow_band_d: { min: 0, max: 1 },
  max_capital_at_risk_pct: { min: 5, max: 100 },
  max_sector_risk_pct: { min: 5, max: 100 },
  max_net_delta_pct: { min: 10, max: 300 },
  dte_watch: { min: 1, max: 45 },
  dte_warning: { min: 0, max: 30 },
  delta_assignment: { min: 0.3, max: 0.95 },
} as ThresholdInfo["bounds"];

const info = (over: Partial<ThresholdInfo> = {}): ThresholdInfo => ({
  defaults,
  bounds,
  overrides: {},
  effective: defaults,
  loosened: [],
  ...over,
});

describe("threshold helpers", () => {
  it("lists only the values that differ from the defaults", () => {
    const form = toThresholdForm(defaults);
    expect(toOverrides(form, defaults)).toEqual({});
    expect(
      toOverrides({ ...form, spread_max_pct: "12", dte_watch: "10" }, defaults),
    ).toEqual({
      spread_max_pct: 12,
      dte_watch: 10,
    });
  });

  it("rejects blanks, out-of-range values and a Warning that is not below the Watch", () => {
    const form = toThresholdForm(defaults);
    const i = info();
    expect(validateThresholds(form, i)).toBeNull();
    expect(validateThresholds({ ...form, spread_max_pct: "" }, i)).toMatch(
      /must be a number/,
    );
    expect(validateThresholds({ ...form, spread_max_pct: "26" }, i)).toMatch(
      /between 1 and 25/,
    );
    expect(validateThresholds({ ...form, dte_warning: "7" }, i)).toMatch(
      /below the Watch/,
    );
  });
});

describe("RuleThresholds", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(settingsApi.thresholdInfo).mockResolvedValue(info());
    vi.mocked(settingsApi.update).mockResolvedValue({} as never);
  });

  it("shows every threshold with its default and allowed range", async () => {
    renderWithClient(<RuleThresholds />);
    expect(await screen.findByLabelText(/Widest bid\/ask spread/)).toHaveValue(
      10,
    );
    expect(screen.getByLabelText(/Minimum open interest/)).toHaveValue(500);
    expect(screen.getAllByText(/Default 10, allowed 1 to 25/)).toHaveLength(1);
  });

  it("saves only what changed", async () => {
    renderWithClient(<RuleThresholds />);
    const field = await screen.findByLabelText(/Widest bid\/ask spread/);
    await userEvent.clear(field);
    await userEvent.type(field, "12");
    await userEvent.click(
      screen.getByRole("button", { name: "Save thresholds" }),
    );
    await waitFor(() =>
      expect(settingsApi.update).toHaveBeenCalledWith({
        thresholds: { spread_max_pct: 12 },
      }),
    );
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("does not save an out-of-range value and says why", async () => {
    renderWithClient(<RuleThresholds />);
    const field = await screen.findByLabelText(/Widest bid\/ask spread/);
    await userEvent.clear(field);
    await userEvent.type(field, "40");
    await userEvent.click(
      screen.getByRole("button", { name: "Save thresholds" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /between 1 and 25/,
    );
    expect(settingsApi.update).not.toHaveBeenCalled();
  });

  it("resets everything to the defaults with an empty object", async () => {
    vi.mocked(settingsApi.thresholdInfo).mockResolvedValue(
      info({
        overrides: { spread_max_pct: 15 },
        effective: { ...defaults, spread_max_pct: 15 },
      }),
    );
    renderWithClient(<RuleThresholds />);
    await screen.findByLabelText(/Widest bid\/ask spread/);
    await userEvent.click(
      screen.getByRole("button", { name: "Reset to defaults" }),
    );
    await waitFor(() =>
      expect(settingsApi.update).toHaveBeenCalledWith({ thresholds: {} }),
    );
  });

  it("warns when a safety rule is looser than the default", async () => {
    vi.mocked(settingsApi.thresholdInfo).mockResolvedValue(
      info({
        loosened: ["open_interest_min"],
        effective: { ...defaults, open_interest_min: 100 },
      }),
    );
    renderWithClient(<RuleThresholds />);
    expect(
      await screen.findByText("Looser than the default."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/1 safety rule\(s\) are set looser/),
    ).toBeInTheDocument();
  });

  it("shows an error when thresholds cannot load", async () => {
    vi.mocked(settingsApi.thresholdInfo).mockRejectedValue(new Error("boom"));
    renderWithClient(<RuleThresholds />);
    expect(
      await screen.findByText("Could not load thresholds."),
    ).toBeInTheDocument();
  });
});
