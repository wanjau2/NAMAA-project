"use client";

/**
 * Persistent navigation. Selected state uses a brand underline and subtle
 * fill (D002 §5), not a dark teal fill. Current page is announced.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { chrome } from "@/lib/copy";
import { useDemoSession } from "@/lib/demo-session";

export function MainNav() {
  const pathname = usePathname();
  const { locale } = useDemoSession();

  if (pathname === "/") return null;

  const links = [
    { href: "/cases", label: chrome(locale, "worklist") },
    { href: "/metrics", label: chrome(locale, "population") },
  ] as const;

  return (
    <nav
      aria-label="Main"
      className="border-b border-border bg-surface px-4 sm:px-6"
    >
      <ul className="mx-auto flex max-w-6xl gap-1">
        {links.map((link) => {
          const active =
            pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "inline-flex items-center border-b-2 px-3 py-2.5 text-sm font-medium",
                  active
                    ? "border-brand bg-subtle text-ink"
                    : "border-transparent text-ink-muted hover:bg-canvas hover:text-ink",
                )}
              >
                {link.label}
                {active ? (
                  <span className="sr-only">
                    {" "}
                    — {chrome(locale, "currentPage")}
                  </span>
                ) : null}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
