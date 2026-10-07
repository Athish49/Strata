"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ComponentProps } from "react";

/** Append the current ?run= (and only that) to internal /app hrefs that don't set their own. */
export function withRunParam(href: string, run: string | null): string {
  if (!run) return href;
  if (href !== "/app" && !href.startsWith("/app/") && !href.startsWith("/app?") && !href.startsWith("/app#")) {
    return href;
  }
  const hashIdx = href.indexOf("#");
  const hash = hashIdx >= 0 ? href.slice(hashIdx) : "";
  const noHash = hashIdx >= 0 ? href.slice(0, hashIdx) : href;
  const qIdx = noHash.indexOf("?");
  const path = qIdx >= 0 ? noHash.slice(0, qIdx) : noHash;
  const params = new URLSearchParams(qIdx >= 0 ? noHash.slice(qIdx + 1) : "");
  if (!params.has("run")) params.set("run", run);
  return `${path}?${params.toString()}${hash}`;
}

export function useAppHref(href: string): string {
  const run = useSearchParams()?.get("run") ?? null;
  return withRunParam(href, run);
}

type AppLinkProps = Omit<ComponentProps<typeof Link>, "href"> & { href: string };

export function AppLink({ href, ...rest }: AppLinkProps) {
  const resolved = useAppHref(href);
  return <Link href={resolved} {...rest} />;
}
