import type { CSSProperties } from 'react'

/**
 * Condense brand mark (codename "Sift"): black input dots arranged in a ring are absorbed into
 * a pulsing purple core, which emits one distilled dot below — "many → one". Inlined SVG; the
 * animation lives in App.css (`@keyframes absorb/coreP/glowP/emit`, scoped under `.brand-mark`)
 * and is disabled under prefers-reduced-motion. Geometry/colors are the locked design handoff.
 */

// 8 input dots on the r=8 ring (N, NE, E, SE, S, SW, W, NW) with a staggered absorb delay.
const ORBS = [
  { x: 0, y: -8, delay: 0 },
  { x: 5.66, y: -5.66, delay: 0.06 },
  { x: 8, y: 0, delay: 0.12 },
  { x: 5.66, y: 5.66, delay: 0.18 },
  { x: 0, y: 8, delay: 0.24 },
  { x: -5.66, y: 5.66, delay: 0.3 },
  { x: -8, y: 0, delay: 0.36 },
  { x: -5.66, y: -5.66, delay: 0.42 },
]

export default function Logo() {
  return (
    <svg
      className="brand-mark"
      viewBox="0 0 32 32"
      role="img"
      aria-label="Condense"
    >
      <circle cx="16" cy="12.5" r="8" fill="none" stroke="#aa3bff" strokeWidth=".6" opacity=".16" />
      <circle className="glow" cx="16" cy="12.5" r="4.5" fill="#aa3bff" opacity=".14" />
      <g fill="#0b0a10">
        {ORBS.map((o) => (
          <circle
            key={`${o.x},${o.y}`}
            className="orb"
            cx="16"
            cy="12.5"
            r="1.15"
            style={
              {
                '--tx': `${o.x}px`,
                '--ty': `${o.y}px`,
                transform: `translate(${o.x}px, ${o.y}px)`,
                animationDelay: `${o.delay}s`,
              } as CSSProperties
            }
          />
        ))}
      </g>
      <circle className="core" cx="16" cy="12.5" r="2.1" fill="#aa3bff" />
      <circle className="out" cx="16" cy="26" r="1.8" fill="#8f1fe6" />
    </svg>
  )
}
