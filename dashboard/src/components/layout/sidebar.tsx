"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/executions", label: "Executions" },
  { href: "/threads", label: "Threads" },
  { href: "/compare", label: "Compare" },
  { href: "/costs", label: "Costs" },
  { href: "/errors", label: "Errors" },
  { href: "/metrics", label: "Metrics" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex w-52 shrink-0 flex-col border-r border-neutral-800 bg-neutral-950 p-4">
      <Link href="/" className="mb-6 block text-lg font-semibold tracking-tight">
        Lang<span className="text-sky-400">Ops</span>
      </Link>
      <nav className="flex flex-col gap-1">
        {LINKS.map((link) => {
          const active =
            link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`rounded px-3 py-2 text-sm ${
                active
                  ? "bg-neutral-800 text-neutral-100"
                  : "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto space-y-2">
        <div className="rounded border border-neutral-800 px-2 py-1.5 text-xs text-neutral-500">
          Press <kbd className="rounded bg-neutral-800 px-1">⌘K</kbd> to search
        </div>
        <p className="text-xs text-neutral-600">Chrome DevTools for LangGraph</p>
      </div>
    </aside>
  );
}
