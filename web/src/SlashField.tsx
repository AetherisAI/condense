import { useEffect, useRef } from 'react'

/**
 * Interactive background: a viewport-filling grid of faint "/" slash marks that rotate to
 * point at the mouse and brighten as the cursor nears them. Native canvas, no deps, no React
 * re-renders (mouse position lives in a ref; drawing is a rAF loop). Sits behind the content
 * with `pointer-events: none`, so it never blocks the UI. Respects prefers-reduced-motion.
 */

// --- tunables (top of file for quick iteration) ---
const SPACING = 32 // px between marks
const LINE = 11 // mark length in px
const BASE_ALPHA = 0.1 // resting opacity (very light grey)
const BOOST = 0.35 // extra opacity right at the cursor
const RADIUS = 140 // px: how far the cursor's "brighten" reaches
const INK = '120, 116, 128' // rgb of --muted, used as rgba(INK, alpha)

export default function SlashField() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvasEl = canvasRef.current
    if (!canvasEl) return
    const canvas: HTMLCanvasElement = canvasEl
    const maybeCtx = canvas.getContext('2d')
    if (!maybeCtx) return
    const ctx: CanvasRenderingContext2D = maybeCtx

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let width = 0
    let height = 0
    let dpr = 1
    // Aim at the viewport centre until the mouse first moves.
    const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 }
    let frame = 0
    let scheduled = false

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = window.innerWidth
      height = window.innerHeight
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      draw()
    }

    function draw() {
      ctx.clearRect(0, 0, width, height)
      ctx.lineCap = 'round'
      ctx.lineWidth = 1.25
      // Centre the grid so the field looks even at any size.
      const offX = ((width % SPACING) + SPACING) / 2
      const offY = ((height % SPACING) + SPACING) / 2
      for (let x = offX; x < width; x += SPACING) {
        for (let y = offY; y < height; y += SPACING) {
          // Reduced motion: a calm, uniform 45° "/" field, no cursor reaction.
          const angle = reduced ? -Math.PI / 4 : Math.atan2(mouse.y - y, mouse.x - x)
          let alpha = BASE_ALPHA
          let len = LINE
          if (!reduced) {
            const d = Math.hypot(mouse.x - x, mouse.y - y)
            if (d < RADIUS) {
              const t = 1 - d / RADIUS
              alpha = BASE_ALPHA + BOOST * t
              len = LINE * (1 + 0.35 * t)
            }
          }
          const dx = (Math.cos(angle) * len) / 2
          const dy = (Math.sin(angle) * len) / 2
          ctx.strokeStyle = `rgba(${INK}, ${alpha})`
          ctx.beginPath()
          ctx.moveTo(x - dx, y - dy)
          ctx.lineTo(x + dx, y + dy)
          ctx.stroke()
        }
      }
    }

    function scheduleDraw() {
      if (scheduled) return
      scheduled = true
      frame = requestAnimationFrame(() => {
        scheduled = false
        draw()
      })
    }

    function onMove(e: MouseEvent) {
      mouse.x = e.clientX
      mouse.y = e.clientY
      scheduleDraw()
    }

    resize()
    window.addEventListener('resize', resize)
    if (!reduced) window.addEventListener('mousemove', onMove, { passive: true })

    return () => {
      window.removeEventListener('resize', resize)
      window.removeEventListener('mousemove', onMove)
      cancelAnimationFrame(frame)
    }
  }, [])

  return <canvas ref={canvasRef} className="slash-field" aria-hidden="true" />
}
