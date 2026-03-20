import Link from "next/link";

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-black/10 bg-white/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          HockeyDeals.ca
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/deals" className="hover:underline">
            Deals
          </Link>
          <Link href="/admin" className="hover:underline">
            Admin
          </Link>
        </nav>
      </div>
    </header>
  );
}

