import { ChangesShell } from "@/components/changes/ChangesShell";

export default function ChangesLayout({ children }: { children: React.ReactNode }) {
  return <ChangesShell>{children}</ChangesShell>;
}
