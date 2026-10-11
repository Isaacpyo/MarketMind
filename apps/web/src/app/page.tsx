"use client";

import { ArrowRight, Layers, Sparkles, TrendingUp } from "lucide-react";
import Link from "next/link";
import { DemoButton } from "@/components/DemoButton";
import { ProductArt } from "@/components/ProductArt";
import { RecommendationRail } from "@/components/RecommendationRail";
import { SkeletonGrid } from "@/components/States";
import { StrategyBadge } from "@/components/StrategyBadge";
import { useAuth } from "@/lib/auth";
import { useCategories, useForYou, useTrending } from "@/lib/hooks";

const STEPS = [
  {
    icon: TrendingUp,
    title: "New shopper",
    body: "With no history, you see what's popular: products bought by the most distinct customers.",
  },
  {
    icon: Layers,
    title: "First clicks",
    body: "After one or two views, TF-IDF over product text finds items like the ones you looked at.",
  },
  {
    icon: Sparkles,
    title: "Three or more items",
    body: "Implicit ALS blends in what shoppers with similar baskets bought. Your vector updates on every request.",
  },
];

function Hero() {
  const { status, user } = useAuth();
  return (
    <section className="grid gap-8 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-950 via-brand-900 to-brand-700 p-6 text-white sm:p-10 lg:grid-cols-[1.3fr_1fr]">
      <div>
        <p className="text-sm font-medium uppercase tracking-wider text-brand-200">Recommendation engine demo</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
          {user ? `Welcome back, ${user.name.split(" ")[0]}` : "A storefront that learns what you like"}
        </h1>
        <p className="mt-4 max-w-xl text-base text-brand-100 sm:text-lg">
          1,000 real products and 140k real purchases from a UK gift shop. The feed blends collaborative filtering
          with content similarity and adapts as you browse.
        </p>
        <div className="mt-6 flex flex-wrap items-start gap-3">
          {status === "anonymous" ? <DemoButton size="lg" /> : null}
          <Link href="/products" className="btn bg-white/10 px-5 py-3 text-base text-white ring-1 ring-white/30 hover:bg-white/20">
            Browse the shop <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
        {user?.is_demo ? (
          <p className="mt-4 max-w-xl rounded-lg bg-white/10 px-4 py-3 text-sm text-brand-50">
            You&apos;re a demo shopper with a real customer&apos;s past orders. Open a few products in a new
            style, then come back here: <strong>For you</strong> recomputes on every visit.
          </p>
        ) : null}
      </div>
      <ol className="grid gap-3 self-center" aria-label="How the For you feed is built">
        {STEPS.map(({ icon: Icon, title, body }, i) => (
          <li key={title} className="flex gap-3 rounded-xl bg-white/10 p-4 ring-1 ring-white/15">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-white/15">
              <Icon className="size-5" aria-hidden="true" />
            </span>
            <div>
              <p className="font-semibold">
                {i + 1}. {title}
              </p>
              <p className="mt-0.5 text-sm text-brand-100">{body}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function ForYou() {
  const { status } = useAuth();
  const feed = useForYou();
  if (status === "anonymous") {
    return (
      <section aria-labelledby="for-you-title" className="card flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 id="for-you-title" className="text-xl font-semibold tracking-tight">
            For you
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Sign in or start the demo to get a personalised feed that explains every pick.
          </p>
        </div>
        <DemoButton />
      </section>
    );
  }
  return (
    <RecommendationRail
      id="for-you"
      title="For you"
      description="Ranked for you right now. Each card says why it was picked."
      badge={feed.data ? <StrategyBadge strategy={feed.data.strategy} /> : null}
      items={feed.data?.items}
      isPending={status === "loading" || feed.isPending}
      error={feed.error}
      onRetry={() => void feed.refetch()}
      context="for_you"
      skeletonCount={12}
    />
  );
}

function Categories() {
  const categories = useCategories();
  return (
    <section aria-labelledby="categories-title" className="space-y-4">
      <h2 id="categories-title" className="text-xl font-semibold tracking-tight">
        Shop by category
      </h2>
      {categories.isPending ? (
        <SkeletonGrid count={6} label="Loading categories" />
      ) : categories.data ? (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {categories.data.map((c) => (
            <li key={c.name}>
              <Link
                href={`/products?category=${encodeURIComponent(c.name)}`}
                className="card flex items-center gap-3 overflow-hidden p-2 pr-3 transition hover:shadow-md"
              >
                <ProductArt productId={c.name} category={c.name} size="sm" className="size-14 shrink-0 rounded-lg" />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-slate-900">{c.name}</span>
                  <span className="text-xs text-slate-500">{c.count} products</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export default function HomePage() {
  const trending = useTrending();
  return (
    <div className="space-y-12">
      <Hero />
      <ForYou />
      <RecommendationRail
        id="trending"
        title="Trending now"
        description="Most-bought products, counted by distinct shoppers."
        items={trending.data?.slice(0, 6)}
        isPending={trending.isPending}
        error={trending.error}
        onRetry={() => void trending.refetch()}
        context="trending"
      />
      <Categories />
    </div>
  );
}
