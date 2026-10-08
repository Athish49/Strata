import type { MatchPath } from "@/lib/api/schemas";
import { matchPathWords, type MatchPathContext } from "@/lib/labels";
import { MATCH_PATH_ICONS } from "@/lib/verdict-tokens";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { NamedIcon } from "./icons";

export interface MatchPathIconProps {
  path: MatchPath;
  /** Fills the plain-words sentence (rule key, register ref, old value). */
  context?: MatchPathContext;
  /** Show the plain words next to the icon instead of only in a tooltip. */
  showWords?: boolean;
  className?: string;
}

/** Match-path icon (link / book / git-branch / repeat) with the plain-words explanation. */
export function MatchPathIcon({ path, context, showWords, className }: MatchPathIconProps) {
  const words = matchPathWords(path, context);
  if (showWords) {
    return (
      <span data-match-path={path} className={cn("inline-flex items-center gap-1.5 text-[13px] text-ink-2", className)}>
        <NamedIcon name={MATCH_PATH_ICONS[path]} aria-hidden className="size-4 shrink-0 text-ink-2" strokeWidth={1.5} />
        {words}
      </span>
    );
  }
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span data-match-path={path} role="img" aria-label={words} tabIndex={0} className={cn("inline-grid size-5 place-items-center text-ink-2", className)}>
          <NamedIcon name={MATCH_PATH_ICONS[path]} aria-hidden className="size-4" strokeWidth={1.5} />
        </span>
      </TooltipTrigger>
      <TooltipContent>{words}</TooltipContent>
    </Tooltip>
  );
}
