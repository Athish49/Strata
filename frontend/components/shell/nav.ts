import {
  Building2,
  FileText,
  Grid3x3,
  GitCompareArrows,
  LayoutGrid,
  Radar,
  ShieldCheck,
  FlaskConical,
  Scale,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: "docs" | "changes";
}

export const ANALYSIS_NAV: NavItem[] = [
  { href: "/app", label: "Overview", icon: LayoutGrid },
  { href: "/app/changes", label: "Changes", icon: GitCompareArrows, badge: "changes" },
  { href: "/app/documents", label: "Documents", icon: FileText, badge: "docs" },
  { href: "/app/matrix", label: "Impact matrix", icon: Grid3x3 },
  { href: "/app/radar", label: "Radar", icon: Radar },
  { href: "/app/what-if", label: "What-if", icon: FlaskConical },
  { href: "/app/trust", label: "Trust", icon: ShieldCheck },
];

export const KB_NAV: NavItem[] = [
  { href: "/app/regulations", label: "Regulations", icon: Scale },
  { href: "/app/company", label: "Company", icon: Building2 },
];

export const FUTURE_NAV_IDS = ["assistant", "agents", "integrations"] as const;

export function isActive(pathname: string, href: string) {
  return href === "/app" ? pathname === "/app" : pathname === href || pathname.startsWith(href + "/");
}

export type { LucideIcon };
