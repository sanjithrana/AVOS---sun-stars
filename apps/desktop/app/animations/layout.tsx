import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { RmHeader } from "@/components/reelmimic/Shell";
// ReelMimic's design system, scoped under .rm so it only styles the Animations tab.
import "@/components/reelmimic/reelmimic.css";

/** Animations tab: the ReelMimic UI (reference video -> new animation in the same style) ported natively into AVOS. */
export default function AnimationsLayout({ children }: { children: ReactNode }) {
  return <AppShell header={<RmHeader />}>{children}</AppShell>;
}
