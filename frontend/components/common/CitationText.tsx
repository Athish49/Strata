import { cn } from "@/lib/utils";

/** A legal citation or clause id in mono. */
export function CitationText({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("font-mono text-[12.5px] leading-[18px] text-ink", className)}>{children}</span>;
}
