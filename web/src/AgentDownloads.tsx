/**
 * "Downloads" — the System drawer group offering the STANDALONE folder agent (a separate
 * Tkinter-GUI/CLI build, `agent/app.py`+`agent/cli.py`, packaged per-OS) for a machine other than
 * this one: a second computer, a headless server, anywhere the Tauri desktop app itself isn't
 * running. Restores the per-OS download rows Arthur's original `AgentMenu.tsx` had (absorbed into
 * `SystemMenu.tsx`'s Folder agent section by D57/Task U6, then lost from view for desktop-app
 * users — the desktop's OWN "Folder agent" section shows live Start/Stop controls for its
 * Tauri-supervised sidecar instead of download links, so a desktop-app user had no in-app way to
 * grab the standalone build for a DIFFERENT machine). Own component file per this WP's brief;
 * mounted in `SystemMenu.tsx` right after the Folder agent section, for every deployment
 * (Tauri desktop or plain browser) — the standalone agent is useful either way.
 *
 * Asset names verified against the live `v0.3.0` GitHub release (`gh release view v0.3.0`, also
 * the current `latest`): `sift-agent-linux-x86_64.AppImage`, `sift-agent-macos.zip`,
 * `sift-agent-windows.zip`. Links use `.../releases/latest/download/<name>` (not a pinned tag) so
 * they keep resolving to whatever the newest release publishes, as long as its asset names stay
 * the same as v0.3.0's — the documented fallback if a future release ever renames them.
 *
 * Every external link routes through `openExternal` (`lib/openExternal.ts`) rather than a bare
 * `<a href>` — inside the real Tauri webview a plain link navigates the app's OWN window instead
 * of escaping to the OS browser, which is exactly the "link does nothing" symptom this avoids.
 */

import type React from 'react'
import { openExternal } from './lib/openExternal'

const RELEASES_URL = 'https://github.com/AetherisAI/condense/releases'
const LATEST_DOWNLOAD_BASE = 'https://github.com/AetherisAI/condense/releases/latest/download'

type AgentBuild = {
  os: string
  hint: string
  asset: string
  note?: string
  icon: React.ReactNode
}

const APPLE = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
    <path d="M16.365 12.9c.02 2.16 1.9 2.88 1.92 2.89-.015.05-.3 1.03-.99 2.04-.6.88-1.22 1.75-2.2 1.77-.96.02-1.27-.57-2.37-.57-1.1 0-1.45.55-2.36.59-.95.03-1.67-.95-2.27-1.83-1.24-1.8-2.18-5.08-.91-7.3.63-1.1 1.76-1.8 2.98-1.82.93-.02 1.81.63 2.38.63.57 0 1.64-.78 2.76-.66.47.02 1.79.19 2.63 1.43-.07.04-1.57.92-1.55 2.73M14.6 6.3c.5-.6.84-1.45.75-2.3-.72.03-1.6.48-2.12 1.08-.47.53-.88 1.4-.77 2.22.8.06 1.63-.41 2.14-1" />
  </svg>
)

const UBUNTU = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
    <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20m0 3.2a6.8 6.8 0 0 1 6.06 3.72 2.02 2.02 0 0 0-.4 3.03 6.8 6.8 0 0 1 0 .1 2.02 2.02 0 0 0 .4 3.03 6.8 6.8 0 0 1-11.03 1.9 2.02 2.02 0 0 0-2.5-1.72A6.8 6.8 0 0 1 4 12a6.8 6.8 0 0 1 .53-2.65 2.02 2.02 0 0 0 2.5-1.72A6.77 6.77 0 0 1 12 5.2m0 3.1a3.7 3.7 0 1 0 0 7.4 3.7 3.7 0 0 0 0-7.4" />
  </svg>
)

const WINDOWS = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
    <path d="M3 5.4 10.5 4.3v7.2H3zM11.5 4.15 21 2.8v8.7h-9.5zM3 12.5h7.5v7.2L3 18.6zM11.5 12.5H21v8.7l-9.5-1.35z" />
  </svg>
)

const AGENT_BUILDS: AgentBuild[] = [
  {
    os: 'macOS',
    hint: 'Apple silicon & Intel · unzip and open',
    asset: 'sift-agent-macos.zip',
    note: 'Unsigned build — first launch: right-click the app → Open.',
    icon: APPLE,
  },
  {
    os: 'Linux',
    hint: 'AppImage · chmod +x, then run — no install',
    asset: 'sift-agent-linux-x86_64.AppImage',
    icon: UBUNTU,
  },
  {
    os: 'Windows',
    hint: 'unzip and run',
    asset: 'sift-agent-windows.zip',
    icon: WINDOWS,
  },
]

function ExternalLink({
  href,
  className,
  children,
}: {
  href: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <a
      href={href}
      className={className}
      onClick={(e) => {
        e.preventDefault()
        void openExternal(href)
      }}
    >
      {children}
    </a>
  )
}

export default function AgentDownloads() {
  return (
    <div className="sys-section">
      <h3 className="sys-heading">Downloads</h3>
      <p className="agent-intro">
        Grab the standalone folder agent for another machine — a second computer, or a headless
        server that isn&apos;t running this app.
      </p>

      {AGENT_BUILDS.map((b) => (
        <div className="agent-dl-row" key={b.os}>
          <span className="agent-dl-icon">{b.icon}</span>
          <span className="agent-dl-meta">
            <span className="agent-dl-os">{b.os}</span>
            <span className="agent-dl-hint">{b.hint}</span>
            {b.note && <span className="agent-note">{b.note}</span>}
          </span>
          <ExternalLink className="agent-dl-btn" href={`${LATEST_DOWNLOAD_BASE}/${b.asset}`}>
            Download
          </ExternalLink>
        </div>
      ))}

      <p className="agent-note">
        Prefer just the engine, no chat UI? Run{' '}
        <code>scripts/install.sh --server-only</code> from a clone of the repo. See the{' '}
        <ExternalLink href={RELEASES_URL}>Releases page</ExternalLink> for every build and its
        checksums.
      </p>
    </div>
  )
}
