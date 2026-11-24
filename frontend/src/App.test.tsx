import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./components/layout", async () => {
  const { Outlet } = await import("react-router-dom");
  return { AppLayout: () => <Outlet /> };
});

vi.mock("./pages/DashboardPage", () => ({
  DashboardPage: () => <div>Dashboard test screen</div>,
}));

vi.mock("./api/endpoints", () => ({
  authApi: { me: vi.fn(), login: vi.fn(), signup: vi.fn() },
}));

import App from "./App";
import { tokenStore } from "./api/client";
import { useAuthStore } from "./store/auth.store";

describe("App development authentication", () => {
  beforeEach(() => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_DEV_AUTH_BYPASS", "true");
    localStorage.clear();
    useAuthStore.setState({ user: null, token: null, loading: false, error: null });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  it("opens the dashboard directly with the development token", async () => {
    render(<App />);

    expect(await screen.findByText("Dashboard test screen")).toBeInTheDocument();
    expect(tokenStore.get()).toBe("dev-admin-token");
    expect(screen.queryByText("Sign in to StrideAlytics")).not.toBeInTheDocument();
  });

  it("keeps login enabled when the development bypass flag is off", async () => {
    vi.stubEnv("VITE_DEV_AUTH_BYPASS", "false");
    render(<App />);

    expect(await screen.findByText("Sign in to StrideAlytics")).toBeInTheDocument();
    expect(tokenStore.get()).toBeNull();
  });
});
