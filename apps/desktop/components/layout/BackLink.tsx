"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { MouseEvent, ReactNode } from "react";

/** Goes back to the page you came from (Library, Jobs, a tab, a search...). Only when there is no earlier page of this app does it go to `href`.
 *  Still a real link, so open-in-new-tab and copy-link keep working. */
export function BackLink({ href, className, children, direct = false }: { href: string; className?: string; children: ReactNode; direct?: boolean }) {
  const router = useRouter();
  const onClick = (e: MouseEvent<HTMLAnchorElement>) => {
    if (direct || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;   // direct: always go to href (a studio's own list)
    let can = false;
    try {
      const nav = (window as unknown as { navigation?: { canGoBack?: boolean } }).navigation;
      can = nav && typeof nav.canGoBack === "boolean" ? nav.canGoBack : window.history.length > 1 && !!document.referrer && document.referrer.startsWith(window.location.origin);
    } catch { /* no history access: use the link */ }
    if (can) { e.preventDefault(); router.back(); }
  };
  return <Link href={href} onClick={onClick} className={className}>{children}</Link>;
}
