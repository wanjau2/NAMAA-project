"use client";

/**
 * Minimal navigation strip. A6 refines this into the full shell; for now it
 * exists so the worklist and population view are reachable without typing URLs.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/cases", label: "Worklist" },
  { href: "/metrics", label: "Population view" },
] as const;

export function MainNav() {
  const pathname = usePathname();

  // Hide on guest entry: the session has not started yet.
  if (pathname === "/") return null;

  return (
    <nav
      aria-label="Main"
      className="border-b border-border bg-surface px-4 sm:px-6"
    >
      <ul className="mx-auto flex max-w-6xl gap-1">
        {LINKS.map((link) => {
          const active =
            pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "inline-block border-b-2 px-3 py-2.5 text-sm font-medium",
                  active
                    ? "border-brand text-ink"
                    : "border-transparent text-ink-muted hover:text-ink",
                )}
              >
                {link.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
