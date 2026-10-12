import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DemoButton } from "@/components/DemoButton";
import { MetricBars } from "@/components/admin/MetricBars";
import { ProductCard } from "@/components/ProductCard";
import { StrategyBadge } from "@/components/StrategyBadge";
import { setAuthToken } from "@/lib/api/client";
import { AuthProvider, useAuth } from "@/lib/auth";
import { makeQueryClient } from "@/lib/query-client";
import { tokenStore } from "@/lib/token-store";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const product = {
  id: "85123A",
  title: "White Hanging Heart T-Light Holder",
  description: "",
  category: "Candles & Lighting",
  price: 2.95,
  popularity: 621,
};

function withProviders(ui: ReactNode) {
  return (
    <QueryClientProvider client={makeQueryClient()}>
      <AuthProvider>{ui}</AuthProvider>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  push.mockReset();
  tokenStore.reset();
  setAuthToken(null);
});

describe("ProductCard", () => {
  it("links to the product and explains the recommendation", () => {
    render(<ProductCard product={product} recommendation={{ source: "content", reason: "Because you viewed “Mug”" }} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/products/85123A");
    expect(screen.getByRole("heading", { name: product.title })).toBeInTheDocument();
    expect(screen.getByText("£2.95")).toBeInTheDocument();
    expect(screen.getByText("Because you viewed “Mug”")).toBeInTheDocument();
  });
});

describe("StrategyBadge", () => {
  it("names the strategy in words, not just colour", () => {
    render(<StrategyBadge strategy="cold_start" />);
    expect(screen.getByText(/Getting to know you/)).toBeInTheDocument();
  });
});

describe("MetricBars", () => {
  it("labels every bar and exposes values to assistive tech", async () => {
    render(
      <MetricBars
        title="Precision@10"
        help="help"
        rows={[
          { model: "popularity", label: "Popularity", value: 0.02 },
          { model: "hybrid", label: "Hybrid (served)", value: 0.06 },
        ]}
      />,
    );
    expect(screen.getByText("6.0%")).toBeInTheDocument();
    const hybrid = screen.getByLabelText("Hybrid (served): 6.0%, 3.0 times popularity");
    await userEvent.tab();
    await userEvent.tab();
    expect(hybrid).toHaveFocus();
    expect(screen.getByText("6.00%")).toBeInTheDocument();
  });
});

function WhoAmI() {
  const { user, status } = useAuth();
  return <p data-testid="who">{status === "authenticated" ? user?.name : status}</p>;
}

describe("DemoButton", () => {
  it("signs in as a demo shopper and stores the session", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "demo-token",
          token_type: "bearer",
          user: { id: "u1", email: "demo@x.dev", name: "Demo Shopper", role: "admin", is_demo: true },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      withProviders(
        <>
          <DemoButton redirectTo="/products" />
          <WhoAmI />
        </>,
      ),
    );
    expect(screen.getByTestId("who")).toHaveTextContent("anonymous");
    await userEvent.click(screen.getByRole("button", { name: "Try the demo" }));
    expect(await screen.findByText("Demo Shopper")).toBeInTheDocument();
    expect(window.localStorage.getItem("marketmind.token")).toBe("demo-token");
    expect(fetchMock.mock.calls[0]![0]).toBe("http://localhost:8000/api/auth/demo");
    expect(push).toHaveBeenCalledWith("/products");
  });

  it("shows the API's error message when the demo can't start", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Too many requests, slow down a little" }), { status: 429 }),
      ),
    );
    render(withProviders(<DemoButton />));
    await userEvent.click(screen.getByRole("button", { name: "Try the demo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many requests, slow down a little");
    expect(push).not.toHaveBeenCalled();
  });
});
