"use client";

/**
 * Case-level location. Main nav still points at the worklist; this strip
 * announces overview / source review / retrieved context.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { chrome } from "@/lib/copy";
import { useDemoSession } from "@/lib/demo-session";

export function CaseSubnav({ caseId }: { caseId: string }) {
  const pathname = usePathname();
  const { locale } = useDemoSession();
  const overview = `/cases/${caseId}`;
  const review = `/cases/${caseId}/review`;
  const context = `/cases/${caseId}/context`;

  const links = [
    { href: overview, label: chrome(locale, "caseOverview"), current: pathname === overview },
    {
      href: review,
      label: chrome(locale, "reviewSource"),
      current: pathname.startsWith(review),
    },
    {
      href: context,
      label: chrome(locale, "retrievedContext"),
      current: pathname.startsWith(context),
    },
  ];

  return (
    <nav aria-label={chrome(locale, "caseSections")} className="mt-4">
      <ul className="flex flex-wrap gap-1 border-b border-border">
        {links.map((link) => (
          <li key={link.href}>
            <Link
              href={link.href}
              aria-current={link.current ? "page" : undefined}
              className={cn(
                "inline-flex items-center border-b-2 px-3 py-2 text-sm font-medium",
                link.current
                  ? "border-brand bg-subtle text-ink"
                  : "border-transparent text-ink-muted hover:bg-canvas hover:text-ink",
              )}
            >
              {link.label}
              {link.current ? (
                <span className="sr-only"> — {chrome(locale, "currentPage")}</span>
              ) : null}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
