# MarketMind: build plan

This replaces the landing-page stub with a working storefront and recommendation engine.

## Scope (MVP)

- A catalogue of about 1,000 real products, seeded from the **UCI Online Retail** dataset (a UK gift
  retailer, 2010–2011, CC BY 4.0). It includes about 3,000 real customers' purchase histories, which act as
  implicit feedback.
- Browsing (search, category filter, sort, pagination), product pages, a cart and checkout (an order is
  created and no payment is taken), and order history.
- Implicit-feedback event tracking: `view` and `rec_click` events come from the client. `add_to_cart` and
  `purchase` events are only emitted by the server, so the client can't fake them.
- A personalised **"For you"** feed that blends ALS (`implicit`) with TF-IDF content similarity.
- **Cold start**: popularity first, then popularity blended with content similarity from the user's first
  few interactions. No retrain is needed.
- Product pages show **"Similar items"** (TF-IDF cosine) and **"Customers also bought"** (ALS item factors).
- An **admin page** shows offline metrics (precision@k, recall@k and catalogue coverage on a temporal
  holdout) for ALS, Hybrid, Content and Popularity. It also lists training runs, and its retrain button
  accepts tunable hyperparameters.
- A one-click **"Try the demo"** login. It creates an isolated, expiring demo shopper with a real
  seeded purchase history.

## Architecture

```
apps/web  (Next.js 16, React 19, TanStack Query, Tailwind)  ->  Netlify
   | HTTPS + JSON, Bearer JWT
apps/api  (FastAPI, pymongo, scikit-learn, implicit)        ->  Render free web service (512 MB)
   |
MongoDB (Atlas M0 in prod, mongo:7 container locally)
packages/api-contract/openapi.json: the API contract; the web app's TS types are generated from it
```

### Why the frontend fetches client-side

Render free services sleep when idle, and a cold start can take 30 to 60 seconds. If pages were
server-rendered against the API, the page would hang blank for that time. Instead, every page renders
immediately and fetches data in the browser. A `ServerStatus` provider pings `/health`. If the ping takes
longer than about 2.5 s, a "Waking the server…" banner explains the delay until the API answers.

### MongoDB collections

| collection      | purpose                                                                 |
|-----------------|-------------------------------------------------------------------------|
| `products`      | `_id` = SKU, title, description, category, price, `popularity`          |
| `users`         | email, bcrypt hash, role (`customer` / `admin`), `is_demo`, `expires_at` |
| `events`        | `user_id`, `product_id`, `type`, `ts`, `source` (`seed`/`live`/`demo_clone`) |
| `carts`         | one document per user with line items                                   |
| `orders`        | immutable order snapshots (prices captured at checkout)                 |
| `training_runs` | status, params, metrics, dataset stats, timings                         |
| `model_artifacts` | serialised item factors (`.npz`, ~250 KB), newest 3 kept            |
| `meta`          | seed version, retrain lock                                              |

Demo users and everything they create carry `expires_at`, and a TTL index cleans them up after 7 days.

### Recommender

- **Interaction matrix**: user × item, with weights summed per pair (`view` 1, `rec_click` 2,
  `add_to_cart` 4, `purchase` 8), then `log1p`. The `demo_clone` events are excluded from training so
  copied histories don't count twice.
- **ALS** (`implicit.cpu.als`): defaults are factors 64, regularisation 0.05, alpha 1.0 and 20 iterations.
  These were tuned on the holdout. Only the item factors are persisted. At request time the user vector
  is recomputed from the user's *current* events (`recalculate_user`), so the feed reacts to browsing
  immediately without a retrain.
- **Content**: a TF-IDF (1–2-grams, sublinear tf, English stop words) over product titles. Adding the
  category lowered holdout precision, so it was left out. It is rebuilt in memory at startup, which
  takes milliseconds for about 1k products.
- **Hybrid serving**:
  - 0 interactions: popularity ("Trending").
  - 1–2 distinct items: 0.7 × content + 0.3 × popularity (both z-scored).
  - 3 or more items: 0.5 × ALS + 0.5 × content (both z-scored).
  - Already-purchased and in-cart items are filtered out. Every item carries a human-readable *reason*.
- **Evaluation**: a temporal holdout that keeps the last 20% of each user's items (users with at least
  5 items). It reports precision@10, recall@10 and coverage for Popularity, Content, ALS and Hybrid. In
  the prototype, Popularity scored 0.024, ALS 0.057, Content 0.066 and Hybrid 0.068 (precision@10).
- **Retraining** runs in a background thread with a lock in Mongo and a cooldown. The final model is
  refit on all data and stored in `model_artifacts` (one document, well under the 16 MB limit), then
  hot-swapped in memory.

### API surface (prefix `/api`)

`GET /health` · `POST /auth/register|login|demo` · `GET /auth/me` · `GET /products` ·
`GET /products/{id}` · `GET /categories` · `GET /products/{id}/similar` · `GET /products/{id}/also-bought` ·
`GET /recommendations/for-you` · `GET /recommendations/trending` · `POST /events` · `GET /cart` ·
`POST /cart/items` · `PUT|DELETE /cart/items/{id}` · `POST /orders` · `GET /orders[/{id}]` ·
`GET /admin/overview` · `GET /admin/runs[/{id}]` · `POST /admin/retrain`

## Testing

- **API**: pytest. Unit tests cover metrics, splitting, weighting, content, hybrid strategy and ALS on
  synthetic data. API tests use FastAPI `TestClient` + `mongomock`, so no database is needed.
- **Web**: Vitest for pure logic (API client and waking detection, formatting). ESLint and `tsc` run too.
- **E2E**: a Playwright smoke test against the real stack (Mongo + API + built Next app). It covers demo
  login, the "For you" feed, a product page, add to cart, checkout and order confirmation.
- **CI**: GitHub Actions runs these jobs: api (ruff, mypy, pytest), web (eslint, tsc, vitest, build),
  e2e, and docker compose build.

## Known trade-offs / tech debt (tracked in README)

- The JWT is stored in `localStorage`, because API and web are on different domains. A same-site
  `api.` subdomain with httpOnly cookies would be stronger.
- Demo shoppers are admins so reviewers can see the retrain flow. Retraining is rate-limited by a
  server-side cooldown, and there are no destructive admin actions.
- Rate limiting is per-process and in memory, which is fine for one instance. Use Redis for more.
- Training runs inside the web process (a thread). At larger scale it should move to a worker/queue.
