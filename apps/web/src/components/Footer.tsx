import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-16 border-t border-slate-200 bg-white">
      <div className="container-page flex flex-col gap-3 py-8 text-sm text-slate-600 sm:flex-row sm:items-center sm:justify-between">
        <p>
          MarketMind is a portfolio demo. No payments are taken. Catalogue and purchase history come from the{" "}
          <a
            className="font-medium text-brand-800 underline-offset-2 hover:underline"
            href="https://archive.ics.uci.edu/dataset/352/online+retail"
            target="_blank"
            rel="noopener noreferrer"
          >
            UCI Online Retail dataset
          </a>{" "}
          (CC BY 4.0).
        </p>
        <Link href="/admin" className="shrink-0 font-medium text-brand-800 underline-offset-2 hover:underline">
          How the model is doing →
        </Link>
      </div>
    </footer>
  );
}
