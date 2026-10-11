"use client";

import clsx from "clsx";
import { LoaderCircle } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useId, useState, type FormEvent } from "react";
import { DemoButton } from "@/components/DemoButton";
import { Spinner } from "@/components/States";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { safeNext } from "@/lib/navigation";

type Mode = "signin" | "register";

function LoginForm() {
  const { signIn, register } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [mode, setMode] = useState<Mode>("signin");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ids = { name: useId(), email: useId(), password: useId(), error: useId() };

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    const name = String(form.get("name") ?? "").trim();
    setPending(true);
    setError(null);
    try {
      if (mode === "signin") await signIn(email, password);
      else await register(name, email, password);
      router.push(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setPending(false);
    }
  }

  const tab = (value: Mode, label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={mode === value}
      onClick={() => {
        setMode(value);
        setError(null);
      }}
      className={clsx(
        "flex-1 rounded-md px-3 py-2 text-sm font-medium transition",
        mode === value ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900",
      )}
    >
      {label}
    </button>
  );

  return (
    <div className="mx-auto grid max-w-4xl gap-6 md:grid-cols-2">
      <section className="card p-6 sm:p-8" aria-labelledby="demo-title">
        <h2 id="demo-title" className="text-lg font-semibold">
          Just looking around?
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          The demo signs you in as a fresh shopper with a real 2011 customer&apos;s purchase history, so the{" "}
          <strong>For you</strong> feed is personalised from the first click. It&apos;s also an admin, so you can
          open the model dashboard and retrain.
        </p>
        <DemoButton className="mt-5" redirectTo={next} size="lg" />
      </section>

      <section className="card p-6 sm:p-8" aria-labelledby="account-title">
        <h1 id="account-title" className="sr-only">
          {mode === "signin" ? "Sign in" : "Create an account"}
        </h1>
        <div role="tablist" aria-label="Account" className="flex gap-1 rounded-lg bg-slate-100 p-1">
          {tab("signin", "Sign in")}
          {tab("register", "Create account")}
        </div>
        <form onSubmit={onSubmit} className="mt-6 space-y-4" aria-describedby={error ? ids.error : undefined} noValidate={false}>
          {mode === "register" ? (
            <div>
              <label htmlFor={ids.name} className="label">
                Name
              </label>
              <input id={ids.name} name="name" className="input" required maxLength={60} autoComplete="name" />
            </div>
          ) : null}
          <div>
            <label htmlFor={ids.email} className="label">
              Email
            </label>
            <input id={ids.email} name="email" type="email" className="input" required autoComplete="email" />
          </div>
          <div>
            <label htmlFor={ids.password} className="label">
              Password
            </label>
            <input
              id={ids.password}
              name="password"
              type="password"
              className="input"
              required
              minLength={mode === "register" ? 8 : 1}
              maxLength={128}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
            />
            {mode === "register" ? <p className="mt-1 text-xs text-slate-500">At least 8 characters.</p> : null}
          </div>
          {error ? (
            <p id={ids.error} role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
              {error}
            </p>
          ) : null}
          <button type="submit" className="btn-primary w-full py-3" disabled={pending}>
            {pending ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null}
            {mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>
      </section>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <LoginForm />
    </Suspense>
  );
}
