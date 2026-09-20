"use client"

import type { ReactNode } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { MessagesSquare, Orbit } from "lucide-react"
import { cn } from "@/lib/utils"
import { Starfield } from "@/components/starfield"

const nav = [
  { href: "/", label: "Agent", icon: MessagesSquare },
]

export function AppFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="relative min-h-dvh">
      <Starfield />

      {/* Desktop / tablet left rail */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-20 flex-col items-center border-r border-border/60 bg-sidebar/70 py-5 backdrop-blur-xl sm:flex">
        <Link href="/" className="group flex flex-col items-center gap-1.5" aria-label="Odd Worlds home">
          <span className="flex size-11 items-center justify-center rounded-xl bg-primary/15 ring-1 ring-primary/30 transition-colors group-hover:bg-primary/25">
            <Orbit className="size-6 text-primary" />
          </span>
          <span className="font-display text-[10px] font-semibold tracking-widest text-foreground/90">
            Odd Worlds
          </span>
        </Link>

        <nav className="mt-8 flex flex-1 flex-col items-center gap-2">
          {nav.map((item) => {
            const active = pathname === item.href
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex w-16 flex-col items-center gap-1 rounded-lg py-2.5 text-[11px] font-medium transition-colors",
                  active
                    ? "bg-primary/15 text-primary ring-1 ring-primary/25"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <Icon className="size-5" />
                {item.label}
              </Link>
            )
          })}
        </nav>

        <p className="px-1 text-center text-[9px] leading-tight text-muted-foreground">
          NASA Exoplanet Archive
        </p>
      </aside>

      {/* Mobile bottom tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-stretch border-t border-border/60 bg-sidebar/85 backdrop-blur-xl sm:hidden">
        {nav.map((item) => {
          const active = pathname === item.href
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-1 text-xs font-medium transition-colors",
                active ? "text-primary" : "text-muted-foreground",
              )}
            >
              <Icon className="size-5" />
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="min-h-dvh pb-16 sm:pb-0 sm:pl-20">{children}</div>
    </div>
  )
}
