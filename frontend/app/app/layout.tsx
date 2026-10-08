import { AppProviders } from "@/lib/providers";
import { AppShell } from "@/components/shell/AppShell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppProviders>
      <AppShell>{children}</AppShell>
    </AppProviders>
  );
}
