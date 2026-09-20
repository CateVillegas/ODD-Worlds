"use client"

import { useMemo } from "react"

// Deterministic pseudo-random so server and client render identical stars
// (avoids hydration mismatch without useEffect).
function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

type Star = {
  top: number
  left: number
  size: number
  duration: number
  delay: number
  bright: boolean
}

function useStars(count: number, seed: number): Star[] {
  return useMemo(() => {
    const rand = mulberry32(seed)
    return Array.from({ length: count }, () => {
      const bright = rand() > 0.82
      return {
        top: rand() * 100,
        left: rand() * 100,
        size: bright ? 1.6 + rand() * 1.4 : 0.6 + rand() * 1.1,
        duration: 2.5 + rand() * 5,
        delay: rand() * 6,
        bright,
      }
    })
  }, [count, seed])
}

export function Starfield() {
  const stars = useStars(140, 20240917)

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* nebula wash */}
      <div className="absolute inset-0 bg-background" />
      <div className="absolute -left-1/4 top-[-10%] h-[70vh] w-[70vh] rounded-full bg-[radial-gradient(circle,oklch(0.4_0.14_290/0.28),transparent_65%)] blur-2xl" />
      <div className="absolute right-[-15%] top-[35%] h-[60vh] w-[60vh] rounded-full bg-[radial-gradient(circle,oklch(0.55_0.11_215/0.2),transparent_65%)] blur-2xl" />
      <div className="absolute bottom-[-20%] left-[25%] h-[55vh] w-[55vh] rounded-full bg-[radial-gradient(circle,oklch(0.6_0.13_310/0.12),transparent_65%)] blur-3xl" />

      {stars.map((s, i) => (
        <span
          key={i}
          className="absolute rounded-full bg-foreground"
          style={{
            top: `${s.top}%`,
            left: `${s.left}%`,
            width: `${s.size}px`,
            height: `${s.size}px`,
            opacity: s.bright ? 0.9 : 0.4,
            boxShadow: s.bright ? "0 0 6px 1px oklch(0.93 0.012 250 / 0.6)" : undefined,
            animation: `twinkle ${s.duration}s ease-in-out ${s.delay}s infinite`,
          }}
        />
      ))}
    </div>
  )
}
