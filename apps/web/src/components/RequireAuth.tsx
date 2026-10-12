"use client";

import { Lock } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { DemoButton } from "@/components/DemoButton";
import { EmptyState, Spinner } from "@/components/States";

export function RequireAuth({ children, what }: { children: ReactNode; what: string }) {
  const { status } = useAuth();
  if (status === "loading") {
    return (
      <div className="py-16 text-center">
        <Spinner label="Checking your session" />
      </div>
    );
  }
  if (status === "anonymous") {
    return (
      <EmptyState
        title={`Sign in to see ${what}`}
        icon={<Lock className="size-10" aria-hidden="true" />}
        action={
          <div className="flex flex-col items-center gap-3 sm:flex-row">
            <DemoButton />
            <Link href="/login" className="btn-secondary">
              Sign in or create an account
            </Link>
          </div>
        }
      >
        Or try the one-click demo account, which comes with a real shopper&apos;s purchase history.
      </EmptyState>
    );
  }
  return <>{children}</>;
}
