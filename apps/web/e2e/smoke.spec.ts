import { expect, test, type Page } from "@playwright/test";

async function startDemo(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("A storefront that learns what you like");
  await page.getByRole("button", { name: "Try the demo" }).first().click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Welcome back, Demo");
}

test("demo shopper: personalised feed → product → cart → order @responsive", async ({ page }) => {
  await startDemo(page);

  // The demo shopper has a real purchase history, so the feed is the ALS + content hybrid.
  const forYou = page.getByRole("region", { name: "For you" });
  await expect(forYou.getByText("Personalised · ALS + content hybrid")).toBeVisible();
  const cards = forYou.getByRole("link");
  await expect(cards).toHaveCount(12);
  await expect(forYou.getByText(/Because you bought|Popular with shoppers who share your taste/).first()).toBeVisible();

  // Open the top recommendation.
  const firstTitle = (await cards.first().getByRole("heading").textContent())?.trim() ?? "";
  await cards.first().click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(firstTitle);
  await expect(page.getByRole("region", { name: "Similar items" }).getByRole("link").first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Customers also bought" }).getByRole("link").first()).toBeVisible();

  // Add it to the cart and check out.
  await page.getByRole("button", { name: "Increase quantity" }).click();
  await page.getByRole("button", { name: "Add to cart" }).click();
  await expect(page.getByText("Added to your cart.")).toBeVisible();
  await page.getByRole("link", { name: "Cart, 2 items" }).click();

  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Your cart");
  const cartItems = page.getByRole("region", { name: "Items in your cart" });
  await expect(cartItems.getByRole("link", { name: firstTitle })).toBeVisible();
  await expect(cartItems.getByRole("combobox")).toHaveValue("2");
  await page.getByRole("button", { name: "Place order" }).click();

  await expect(page.getByText("Thanks! Your order has been placed.")).toBeVisible();
  await expect(page.getByRole("table").getByRole("link", { name: firstTitle })).toBeVisible();

  // The new order is listed alongside the shopper's historical ones, and the cart is empty.
  await page.goto("/orders");
  await expect(page.getByRole("link", { name: new RegExp(firstTitle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).first()).toBeVisible();
  await page.goto("/cart");
  await expect(page.getByText("Your cart is empty")).toBeVisible();

  // No horizontal scrolling at any width.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("new shopper: popularity first, then content-based cold start after a view", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto("/login");
  await page.getByRole("tab", { name: "Create account" }).click();
  await page.getByLabel("Name").fill("Eve");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct horse battery");
  await page.getByRole("button", { name: "Create account" }).click();

  const forYou = page.getByRole("region", { name: "For you" });
  await expect(forYou.getByText("Trending picks · browse to personalise")).toBeVisible();

  await page.goto("/products?q=heart%20holder");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Results for “heart holder”");
  await page.getByRole("link", { name: /White Hanging Heart T-Light Holder/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("White Hanging Heart T-Light Holder");

  await page.getByRole("link", { name: "MarketMind" }).click();
  await expect(forYou.getByText("Getting to know you · content + popularity")).toBeVisible();
  await expect(forYou.getByText("Because you viewed “White Hanging Heart T-Light Holder”").first()).toBeVisible();
});

test("admin dashboard shows holdout metrics and retrains the model", async ({ page }) => {
  await startDemo(page);
  await page.getByRole("link", { name: "Model admin" }).click();
  await expect(page.getByRole("heading", { name: "Offline evaluation" })).toBeVisible();
  await expect(page.getByText("Served model: precision@10")).toBeVisible();
  await expect(page.getByRole("listitem", { name: /^Hybrid \(served\): \d/ }).first()).toBeVisible();

  // The e2e stack runs with RETRAIN_COOLDOWN_SECONDS=0 (production uses a cooldown).
  await page.getByLabel("Iterations").fill("10");
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/admin/retrain") && r.request().method() === "POST"),
    page.getByRole("button", { name: "Retrain model" }).click(),
  ]);
  expect(response.status()).toBe(202);
  const run = (await response.json()) as { id: string };
  const row = page.getByRole("region", { name: "Training runs" }).getByRole("row", { name: new RegExp(run.id.slice(-8)) });
  await expect(row).toContainText(/admin/i);
  await expect(row).toContainText("it=10");
  await expect(row).toContainText("Succeeded", { timeout: 60_000 });
});
