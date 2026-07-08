import { useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

const TIP_WIDTH = 230
const VIEWPORT_MARGIN = 8

/**
 * Info-icon (ⓘ) that reveals a one-line explanation on hover/focus, rendered through a React
 * portal straight to `document.body` with `position: fixed`, positioned from the icon's own
 * `getBoundingClientRect()` and clamped inside the viewport.
 *
 * This exists because the previous CSS-only tooltip (`.mode-tip`/`.sys-tip`, anchored with
 * `position:absolute; right:-8px` relative to whichever row it sat in) got clipped by the System
 * drawer's own `.drawer-body{overflow-y:auto}` — an explicit `overflow-y` forces the *implicit*
 * `overflow-x` to compute to `auto` too (CSS Overflow spec), so any tooltip wide enough to spill
 * past the drawer's left edge got silently truncated there, worse on narrower drawers/viewports.
 * A `position:fixed` element positioned via JS and portaled OUTSIDE the scrolling ancestor can
 * never be clipped by it again, regardless of drawer width or which column the trigger sits in.
 */
export default function SettingsTooltip({ text }: { text: string }) {
  const iconRef = useRef<HTMLSpanElement>(null)
  const [visible, setVisible] = useState(false)
  const [pos, setPos] = useState<{ left: number; top: number; placement: 'above' | 'below' } | null>(null)

  useLayoutEffect(() => {
    if (!visible || !iconRef.current) return
    const rect = iconRef.current.getBoundingClientRect()
    let left = rect.left + rect.width / 2 - TIP_WIDTH / 2
    left = Math.max(VIEWPORT_MARGIN, Math.min(left, window.innerWidth - TIP_WIDTH - VIEWPORT_MARGIN))
    // Prefer opening above the icon (matches the old tooltip's feel); flip below when there isn't
    // reasonably enough room above (near the top of the drawer/viewport).
    const placement: 'above' | 'below' = rect.top > 90 ? 'above' : 'below'
    const top = placement === 'above' ? rect.top - 8 : rect.bottom + 8
    setPos({ left, top, placement })
  }, [visible])

  return (
    <span
      ref={iconRef}
      className="mode-info sys-info"
      tabIndex={0}
      role="note"
      aria-label={text}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      ⓘ
      {visible &&
        pos &&
        createPortal(
          <span
            className={`sys-tip-portal${pos.placement === 'below' ? ' sys-tip-portal-below' : ''}`}
            role="tooltip"
            style={{ left: pos.left, top: pos.top }}
          >
            {text}
          </span>,
          document.body,
        )}
    </span>
  )
}
