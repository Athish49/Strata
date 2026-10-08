import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-canvas px-6 text-center">
      <p className="font-serif text-[36px] leading-[44px] text-ink">This page could not be found</p>
      <p className="max-w-[420px] text-[14px] leading-5 text-ink-3">The link may be mistyped, or the page may have moved.</p>
      <Link href="/app" className="mt-2 text-[14px] text-ink underline underline-offset-4">
        Back to the overview
      </Link>
    </main>
  );
}
