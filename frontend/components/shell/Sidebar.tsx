"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen, Search } from "lucide-react";
import { AppLink } from "@/lib/app-link";
import { useRunContext } from "@/lib/run-context";
import { FutureCue } from "@/components/common/FutureCue";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { ANALYSIS_NAV, FUTURE_NAV_IDS, KB_NAV, isActive, type NavItem } from "./nav";
import { CompanyChip } from "./CompanyChip";
import { Recents } from "./Recents";
import { useShell } from "./ShellContext";

function useBadges(): Record<string, { n: number; hot: boolean } | undefined> {
  const { run } = useRunContext();
  if (!run) return {};
  return {
    docs: { n: run.stats.docs_flagged, hot: run.stats.docs_flagged > 0 },
    changes: { n: run.stats.in_footprint, hot: false },
  };
}

function Badge({ n, hot }: { n: number; hot: boolean }) {
  return (
    <span
      className={cn(
        "ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-[6px] px-1.5 text-[12px] font-medium tabular-nums",
        hot ? "bg-red-soft text-red" : "bg-sidebar-active text-sidebar-muted",
      )}
    >
      {n}
    </span>
  );
}

function NavRow({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const pathname = usePathname();
  const badges = useBadges();
  const active = isActive(pathname, item.href);
  const badge = item.badge ? badges[item.badge] : undefined;
  const Icon = item.icon;
  const link = (
    <AppLink
      href={item.href}
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? item.label : undefined}
      className={cn(
        "flex items-center rounded-[8px] text-[15px] leading-5 text-sidebar-fg transition-colors duration-150",
        collapsed ? "size-9 justify-center" : "h-8 gap-3 px-3",
        active ? "bg-sidebar-active" : "hover:bg-sidebar-active/60",
      )}
    >
      <Icon className="size-4 shrink-0 text-sidebar-muted" strokeWidth={1.5} />
      {!collapsed && <span className="truncate">{item.label}</span>}
      {!collapsed && badge && <Badge {...badge} />}
    </AppLink>
  );
  if (!collapsed) return link;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{item.label}</TooltipContent>
    </Tooltip>
  );
}

function SearchButton({ className }: { className?: string }) {
  const { setSearchOpen } = useShell();
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="Search"
          onClick={() => setSearchOpen(true)}
          className={cn(
            "grid size-8 place-items-center rounded-[8px] text-sidebar-fg transition-colors duration-150 hover:bg-sidebar-active",
            className,
          )}
        >
          <Search className="size-4" strokeWidth={1.5} />
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom">Search · Ctrl K</TooltipContent>
    </Tooltip>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="px-7 pb-1.5 text-[13px] leading-4 text-sidebar-muted">{children}</div>;
}

function CollapseToggle({ collapsed }: { collapsed: boolean }) {
  const { toggleCollapsed } = useShell();
  const Icon = collapsed ? PanelLeftOpen : PanelLeftClose;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "grid size-8 place-items-center rounded-[8px] text-sidebar-muted transition-colors duration-150 hover:bg-sidebar-active hover:text-sidebar-fg",
          )}
        >
          <Icon className="size-4" strokeWidth={1.5} />
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">{collapsed ? "Expand sidebar" : "Collapse sidebar"}</TooltipContent>
    </Tooltip>
  );
}

export function Sidebar() {
  const { collapsed } = useShell();

  if (collapsed) {
    return (
      <aside
        aria-label="Primary"
        className="flex h-full w-16 shrink-0 flex-col items-center bg-sidebar py-5 text-sidebar-fg"
      >
        <Link
          href="/app"
          aria-label="Strata home"
          className="grid size-9 place-items-center font-serif text-[24px] font-medium leading-none"
        >
          S
        </Link>
        <nav className="mt-6 flex flex-col items-center gap-1">
          {ANALYSIS_NAV.map((i) => (
            <NavRow key={i.href} item={i} collapsed />
          ))}
          <div aria-hidden className="my-2 h-px w-6 bg-sidebar-border" />
          {KB_NAV.map((i) => (
            <NavRow key={i.href} item={i} collapsed />
          ))}
        </nav>
        <div className="mt-auto flex flex-col items-center gap-2">
          <SearchButton />
          <FutureCue id="notifications" variant="icon" onDark side="right" />
          <CollapseToggle collapsed />
          <div className="mt-1">
            <CompanyChip collapsed />
          </div>
        </div>
      </aside>
    );
  }

  return (
    <aside aria-label="Primary" className="flex h-full w-[264px] shrink-0 flex-col bg-sidebar text-sidebar-fg">
      <div className="flex h-[88px] shrink-0 items-center justify-between pl-6 pr-4 pt-2">
        <Link href="/app" className="font-serif text-[24px] font-medium leading-7 tracking-[-0.005em] text-sidebar-fg">
          Strata
        </Link>
        <div className="flex items-center gap-0.5">
          <FutureCue id="notifications" variant="icon" onDark side="bottom" />
          <SearchButton />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pb-4">
        <nav aria-label="Analysis" className="flex flex-col gap-0.5 px-4">
          {ANALYSIS_NAV.map((i) => (
            <NavRow key={i.href} item={i} collapsed={false} />
          ))}
        </nav>

        <div className="mt-7">
          <SectionLabel>Knowledge base</SectionLabel>
          <nav aria-label="Knowledge base" className="flex flex-col gap-0.5 px-4">
            {KB_NAV.map((i) => (
              <NavRow key={i.href} item={i} collapsed={false} />
            ))}
          </nav>
        </div>

        <Recents />

        <div className="mt-7">
          <SectionLabel>Coming soon</SectionLabel>
          <div className="flex flex-col gap-0.5 px-4">
            {FUTURE_NAV_IDS.map((id) => (
              <FutureCue key={id} id={id} variant="nav" onDark />
            ))}
          </div>
        </div>
      </div>

      <div className="flex shrink-0 items-center justify-between border-t border-sidebar-border px-4 py-3">
        <div className="min-w-0 flex-1">
          <CompanyChip />
        </div>
        <CollapseToggle collapsed={false} />
      </div>
    </aside>
  );
}
