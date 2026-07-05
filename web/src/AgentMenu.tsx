import { useEffect } from 'react'

/** One downloadable build of the desktop ingestion agent. */
type Build = {
  os: string
  hint: string
  href?: string // absent → "coming soon"
  note?: string // extra line under the row (e.g. the unsigned-app caveat)
  icon: React.ReactNode
}

const APPLE = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
    <path d="M16.365 12.9c.02 2.16 1.9 2.88 1.92 2.89-.015.05-.3 1.03-.99 2.04-.6.88-1.22 1.75-2.2 1.77-.96.02-1.27-.57-2.37-.57-1.1 0-1.45.55-2.36.59-.95.03-1.67-.95-2.27-1.83-1.24-1.8-2.18-5.08-.91-7.3.63-1.1 1.76-1.8 2.98-1.82.93-.02 1.81.63 2.38.63.57 0 1.64-.78 2.76-.66.47.02 1.79.19 2.63 1.43-.07.04-1.57.92-1.55 2.73M14.6 6.3c.5-.6.84-1.45.75-2.3-.72.03-1.6.48-2.12 1.08-.47.53-.88 1.4-.77 2.22.8.06 1.63-.41 2.14-1"/>
  </svg>
)

const UBUNTU = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
    <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20m0 3.2a6.8 6.8 0 0 1 6.06 3.72 2.02 2.02 0 0 0-.4 3.03 6.8 6.8 0 0 1 0 .1 2.02 2.02 0 0 0 .4 3.03 6.8 6.8 0 0 1-11.03 1.9 2.02 2.02 0 0 0-2.5-1.72A6.8 6.8 0 0 1 4 12a6.8 6.8 0 0 1 .53-2.65 2.02 2.02 0 0 0 2.5-1.72A6.77 6.77 0 0 1 12 5.2m0 3.1a3.7 3.7 0 1 0 0 7.4 3.7 3.7 0 0 0 0-7.4"/>
  </svg>
)

const WINDOWS = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
    <path d="M3 5.4 10.5 4.3v7.2H3zM11.5 4.15 21 2.8v8.7h-9.5zM3 12.5h7.5v7.2L3 18.6zM11.5 12.5H21v8.7l-9.5-1.35z"/>
  </svg>
)

const BUILDS: Build[] = [
  {
    os: 'macOS',
    hint: 'Apple silicon & Intel · unzip and open',
    href: '/downloads/sift-agent-macos.zip',
    note: 'Unsigned build — first launch: right-click the app → Open.',
    icon: APPLE,
  },
  {
    os: 'Ubuntu / Linux',
    hint: 'AppImage · chmod +x, then run — no install',
    href: '/downloads/sift-agent-ubuntu.AppImage',
    icon: UBUNTU,
  },
  {
    os: 'Windows',
    hint: 'unzip and run',
    href: 'https://github.com/AetherisAI/condense/releases/latest/download/sift-agent-windows.zip',
    note: 'Published to the latest GitHub release (built by the build-agent workflow).',
    icon: WINDOWS,
  },
]

/**
 * A "Download the agent" drawer offering the desktop ingestion agent for each OS. Downloads are
 * public static files under /downloads (no token). Its own chip trigger is gone (D57/Task U1;
 * temporary until U6 absorbs this into the System drawer) — `open` is controlled from the
 * workbench topbar's "Agent" button. Closes on backdrop-click or Escape.
 */
export default function AgentMenu({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  // Dismiss on Escape while open — outside clicks are caught by the drawer backdrop.
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onOpenChange(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  return (
    <>
      {open && <div className="drawer-backdrop" onClick={() => onOpenChange(false)} />}

      <aside
        className={`drawer${open ? ' open' : ''}`}
        role="dialog"
        aria-label="Download agent"
        aria-hidden={!open}
      >
        <div className="drawer-head">
          <h2>Agent</h2>
          <button
            type="button"
            className="drawer-close"
            onClick={() => onOpenChange(false)}
            aria-label="Close agent panel"
          >
            ✕
          </button>
        </div>

        <div className="drawer-body">
          <p className="agent-intro">
            Run the ingestion agent on your machine — point it at folders and it keeps them indexed
            in Condense, automatically.
          </p>

          {BUILDS.map((b) => (
            <div className="agent-dl-row" key={b.os}>
              <span className="agent-dl-icon">{b.icon}</span>
              <span className="agent-dl-meta">
                <span className="agent-dl-os">{b.os}</span>
                <span className="agent-dl-hint">{b.hint}</span>
                {b.note && <span className="agent-note">{b.note}</span>}
              </span>
              {b.href ? (
                <a className="agent-dl-btn" href={b.href} download>
                  Download
                </a>
              ) : (
                <span className="agent-dl-btn is-soon" aria-disabled="true">
                  Soon
                </span>
              )}
            </div>
          ))}
        </div>
      </aside>
    </>
  )
}
