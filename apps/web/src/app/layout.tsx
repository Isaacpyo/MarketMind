import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { Providers } from "@/components/Providers";
import { WakeBanner } from "@/components/WakeBanner";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "MarketMind: a storefront that learns what you like", template: "%s · MarketMind" },
  description:
    "E-commerce storefront with a hybrid recommendation engine: implicit ALS collaborative filtering, TF-IDF content similarity and popularity for cold start.",
};

export const viewport: Viewport = {
  themeColor: "#6d28d9",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-GB">
      <body className="flex min-h-dvh flex-col">
        <a
          href="#main"
          className="sr-only z-50 rounded-md bg-white px-4 py-2 font-medium text-brand-800 shadow focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
        >
          Skip to content
        </a>
        <Providers>
          <Header />
          <WakeBanner />
          <main id="main" className="container-page flex-1 py-6 sm:py-8">
            {children}
          </main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
