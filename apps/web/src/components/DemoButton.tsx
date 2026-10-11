"use client";

import clsx from "clsx";
import { LoaderCircle, Wand2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";

/** One click: creates an isolated demo shopper with a real 2011 purchase history. */
export function DemoButton({
  className,
  redirectTo = "/",
  size = "md",
}: {
  className?: string;
  redirectTo?: string;
  size?: "md" | "lg";
}) {
  const { startDemo } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setPending(true);
    setError(null);
    try {
      await startDemo();
      router.push(redirectTo);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start the demo. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className={clsx("flex flex-col items-start gap-2", className)}>
      <button
        type="button"
        onClick={onClick}
        disabled={pending}
        className={clsx("btn-primary", size === "lg" && "px-5 py-3 text-base")}
      >
        {pending ? (
          <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        ) : (
          <Wand2 className="size-4" aria-hidden="true" />
        )}
        {pending ? "Starting demo…" : "Try the demo"}
      </button>
      {error ? (
        <p role="alert" className="text-sm text-rose-700">
          {error}
        </p>
      ) : null}
    </div>
  );
}
