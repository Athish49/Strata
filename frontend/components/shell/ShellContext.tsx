"use client";
import * as React from "react";

interface ShellState {
  collapsed: boolean;
  toggleCollapsed: () => void;
  /** Pages call useAutoCollapseSidebar() instead of using these directly. */
  _setAuto: (v: boolean) => void;
  searchOpen: boolean;
  setSearchOpen: (v: boolean) => void;
  shortcutsOpen: boolean;
  setShortcutsOpen: (v: boolean) => void;
}

const Ctx = React.createContext<ShellState | null>(null);
const KEY = "strata.sidebar.collapsed";

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [userCollapsed, setUserCollapsed] = React.useState(false);
  const [auto, setAuto] = React.useState<boolean | null>(null);
  const [searchOpen, setSearchOpen] = React.useState(false);
  const [shortcutsOpen, setShortcutsOpen] = React.useState(false);

  React.useEffect(() => {
    try {
      if (localStorage.getItem(KEY) === "1") setUserCollapsed(true); // eslint-disable-line react-hooks/set-state-in-effect
    } catch {}
  }, []);

  const collapsed = auto ?? userCollapsed;
  const toggleCollapsed = React.useCallback(() => {
    if (auto !== null) {
      setAuto(!auto);
      return;
    }
    setUserCollapsed((c) => {
      try {
        localStorage.setItem(KEY, c ? "0" : "1");
      } catch {}
      return !c;
    });
  }, [auto]);

  const value = React.useMemo(
    () => ({
      collapsed,
      toggleCollapsed,
      _setAuto: (v: boolean) => setAuto(v ? true : null),
      searchOpen,
      setSearchOpen,
      shortcutsOpen,
      setShortcutsOpen,
    }),
    [collapsed, toggleCollapsed, searchOpen, shortcutsOpen],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useShell() {
  const c = React.useContext(Ctx);
  if (!c) throw new Error("useShell must be used inside <AppShell>");
  return c;
}

/**
 * The reader calls this to collapse the sidebar to the 64px rail while mounted.
 * The user can still toggle it back open; leaving the page restores their own preference.
 */
export function useAutoCollapseSidebar(enabled = true) {
  const { _setAuto } = useShell();
  React.useEffect(() => {
    if (!enabled) return;
    _setAuto(true);
    return () => _setAuto(false);
  }, [enabled, _setAuto]);
}
