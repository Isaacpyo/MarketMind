import Link from "next/link";

export default function NotFound() {
  return (
    <div className="card mx-auto max-w-lg px-6 py-12 text-center">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <p className="mt-2 text-slate-600">That page doesn&apos;t exist. It may have moved.</p>
      <Link href="/" className="btn-primary mt-6">
        Back to the shop
      </Link>
    </div>
  );
}
