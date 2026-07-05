import Logo from './Logo'

/**
 * The workbench's sticky top bar (D57/Task U1): the small animated Condense mark + wordmark on
 * the left (the brand once the empty-state hero has collapsed — see `Chat.tsx`'s `.hero`), and a
 * right-hand cluster of buttons that open the EXISTING drawers/components unchanged — this file
 * only owns the triggers, never the drawer contents (`SystemMenu`/`Library`/`ChatHistory` keep
 * their own markup, just rendered elsewhere with their `open` state lifted here so a single
 * button per drawer can live in one place instead of four floating chips). The standalone "Agent"
 * button/drawer is retired (D57/Task U6) — its downloads now live inside the System drawer's
 * "Folder agent" section.
 */
export default function TopBar({
  hasTurns,
  busy,
  historyOpen,
  onHistoryClick,
  onNewChat,
  libraryOpen,
  onLibraryClick,
  systemOpen,
  onSystemClick,
}: {
  hasTurns: boolean
  // The living-logo status indicator (D57/Task U4) — true while ANY request is in flight (Ask
  // send/stream, Find query, ingest upload), lifted from `Chat`'s combined `isBusy`. Toggles
  // `.mark-busy` on the wrapping element rather than on `Logo` itself, so the mark's own locked
  // markup/animation (`Logo.tsx`) never has to change — only the CSS reached via descendant
  // selectors (`App.css`) does.
  busy: boolean
  historyOpen: boolean
  onHistoryClick: () => void
  onNewChat: () => void
  libraryOpen: boolean
  onLibraryClick: () => void
  systemOpen: boolean
  onSystemClick: () => void
}) {
  return (
    <header className="topbar">
      <div className={`topbar-brand${busy ? ' mark-busy' : ''}`}>
        <Logo />
        <span className="topbar-word">Condense</span>
      </div>

      <div className="topbar-actions">
        <button
          type="button"
          className="topbar-btn"
          onClick={onHistoryClick}
          aria-expanded={historyOpen}
        >
          History
        </button>
        {hasTurns && (
          <button type="button" className="topbar-btn" onClick={onNewChat}>
            New chat
          </button>
        )}
        <button
          type="button"
          className="topbar-btn"
          onClick={onLibraryClick}
          aria-expanded={libraryOpen}
        >
          Library
        </button>
        <button
          type="button"
          className="topbar-btn"
          onClick={onSystemClick}
          aria-expanded={systemOpen}
        >
          System
        </button>
      </div>
    </header>
  )
}
