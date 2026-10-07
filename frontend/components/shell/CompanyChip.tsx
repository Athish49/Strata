import { FutureCue } from "@/components/common/FutureCue";

export function CompanyChip({ collapsed }: { collapsed?: boolean }) {
  const mono = (
    <span
      aria-hidden
      className="grid size-6 shrink-0 place-items-center rounded-[4px] bg-sidebar-fg font-serif text-[14px] font-medium leading-none text-sidebar"
    >
      R
    </span>
  );
  if (collapsed) {
    return (
      <div className="grid place-items-center" title="Rockridge Power & Light">
        {mono}
      </div>
    );
  }
  return (
    <div className="flex h-10 items-center gap-3 px-3">
      {mono}
      <span className="min-w-0 flex-1 truncate text-[15px] leading-5 text-sidebar-fg">Rockridge Power &amp; Light</span>
      <FutureCue id="workspace-switcher" variant="icon" onDark side="top" />
    </div>
  );
}
