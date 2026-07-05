import Logo from './Logo'

/**
 * The workbench's sticky top bar (D57/Task U1): the small animated Condense mark + wordmark on
 * the left (the brand once the empty-state hero has collapsed — see `Chat.tsx`'s `.hero`), and a
 * right-hand cluster of buttons that open the EXISTING drawers/components unchanged — this file
 * only owns the triggers, never the drawer contents (`SystemMenu`/`AgentMenu`/`Library`/
 * `ChatHistory` keep their own markup, just rendered elsewhere with their `open` state lifted
 * here so a single button per drawer can live in one place instead of four floating chips).
 */
export default function TopBar({
  hasTurns,
  historyOpen,
  onHistoryClick,
  onNewChat,
  libraryOpen,
  onLibraryClick,
  agentOpen,
  onAgentClick,
  systemOpen,
  onSystemClick,
}: {
  hasTurns: boolean
  historyOpen: boolean
  onHistoryClick: () => void
  onNewChat: () => void
  libraryOpen: boolean
  onLibraryClick: () => void
  agentOpen: boolean
  onAgentClick: () => void
  systemOpen: boolean
  onSystemClick: () => void
}) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
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
          onClick={onAgentClick}
          aria-expanded={agentOpen}
        >
          Agent
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
