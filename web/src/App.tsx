import { useEffect, useRef, useState } from 'react'
import Library from './Library'
import Chat, { type ChatHandle } from './Chat'
import SlashField from './SlashField'
import SystemMenu from './SystemMenu'
import AgentMenu from './AgentMenu'
import TopBar from './TopBar'
import './App.css'

/**
 * Top-level shell — "the workbench" (D57/Task U1): a single 100svh grid (sticky topbar / the
 * conversation stream, the ONLY scrollable region / a fixed composer, both inside `Chat`). Chat
 * IS the page now — the old Search|Chat tab pill and boxed chat card are gone; `Search`/`Ingest`
 * stay in the tree for U2/U3 to absorb but are not mounted here. Holds the one shared bearer
 * token (entered in the System drawer, persisted to localStorage) plus which drawer (if any) is
 * open — lifted up here so a single topbar button per drawer replaces the old floating chips,
 * without touching the drawers' own markup/behavior.
 */
export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('bearerToken') ?? '')
  const [hasTurns, setHasTurns] = useState(false)
  // The living-logo status indicator (D57/Task U4) — combined Ask/Find/ingest in-flight flag,
  // computed and reported up by `Chat` (`onBusyChange`); `TopBar` just renders it as a class
  // toggle, it never needs to know WHICH flow is running.
  const [isBusy, setIsBusy] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [agentOpen, setAgentOpen] = useState(false)
  const [systemOpen, setSystemOpen] = useState(false)
  const chatRef = useRef<ChatHandle>(null)

  // Persist the token so it doesn't have to be re-entered on every page refresh.
  useEffect(() => {
    localStorage.setItem('bearerToken', token)
  }, [token])

  return (
    <>
      <SlashField />

      <div className="workbench">
        <TopBar
          hasTurns={hasTurns}
          busy={isBusy}
          historyOpen={historyOpen}
          onHistoryClick={() => setHistoryOpen(true)}
          onNewChat={() => chatRef.current?.newChat()}
          libraryOpen={libraryOpen}
          onLibraryClick={() => setLibraryOpen(true)}
          agentOpen={agentOpen}
          onAgentClick={() => setAgentOpen(true)}
          systemOpen={systemOpen}
          onSystemClick={() => setSystemOpen(true)}
        />

        <Chat
          ref={chatRef}
          token={token}
          historyOpen={historyOpen}
          onHistoryOpenChange={setHistoryOpen}
          onTurnsChange={setHasTurns}
          onBusyChange={setIsBusy}
        />
      </div>

      <SystemMenu token={token} setToken={setToken} open={systemOpen} onOpenChange={setSystemOpen} />
      <AgentMenu open={agentOpen} onOpenChange={setAgentOpen} />
      <Library token={token} open={libraryOpen} onOpenChange={setLibraryOpen} />
    </>
  )
}
