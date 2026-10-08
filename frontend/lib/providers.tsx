"use client";
import { Suspense, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { RunProvider } from "@/lib/run-context";

export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <NuqsAdapter>
        {/* useSearchParams (nuqs, AppLink) needs a Suspense boundary during prerender. */}
        <Suspense fallback={null}>
          <RunProvider>{children}</RunProvider>
        </Suspense>
      </NuqsAdapter>
    </QueryClientProvider>
  );
}
