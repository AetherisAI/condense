import { useCallback, useEffect, useRef, useState } from 'react'
import Library from './Library'
import Chat, { type ChatHandle } from './Chat'
import SlashField from './SlashField'
import SystemMenu, { type SystemMenuHandle } from './SystemMenu'
import SetupWizard from './SetupWizard'
import TopBar from './TopBar'
import { isTauri } from './platform'
import { setApiBase } from './api'
import { backendStateKind, backendStatus, listenEvent, type AppConfig, type BackendStateEvent } from './tauri'
import './App.css'

/**
 * Top-level shell — "the workbench" (D57/Task U1): a single 100svh grid (sticky topbar / the
 * conversation stream, the ONLY scrollable region / a fixed composer, both inside `Chat`). Chat
 * IS the page now — the old Search|Chat tab pill and boxed chat card are gone; `Search`/`Ingest`
 * stay in the tree for U2/U3 to absorb but are not mounted here. Holds the one shared bearer
 * token (entered in the System drawer, persisted to localStorage) plus which drawer (if any) is
 * open — lifted up here so a single topbar button per drawer replaces the old floating chips,
 * without touching the drawers' own markup/behavior. The standalone Agent drawer is retired
 * (D57/Task U6) — its downloads now live inside `SystemMenu`'s own "Folder agent" section, opened
 * (and scrolled to) via `openAgentSection` below when the empty-corpus nudge's "Get the agent"
 * button is clicked.
 */
export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('bearerToken') ?? '')
  const [hasTurns, setHasTurns] = useState(false)
  // The living-logo status indicator (D57/Task U4) — combined Ask/Find/ingest in-flight flag,
  // computed and reported up by `Chat` (`onBusyChange`); `TopBar` just renders it as a class
  // toggle, it never needs to know WHICH flow is running.
  const [isBusy, setIsBusy] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  // Library's open state persists across reloads (D57/Task U5) — History/System stay
  // session-only (reopened via their topbar button same as before); Library is the one drawer
  // worth keeping open across a refresh since browsing the corpus is often a standalone task.
  const [libraryOpen, setLibraryOpen] = useState(() => localStorage.getItem('libraryOpen') === 'true')
  const [systemOpen, setSystemOpen] = useState(false)
  const chatRef = useRef<ChatHandle>(null)
  const systemMenuRef = useRef<SystemMenuHandle>(null)

  // Tauri desktop shell only (D60/T2): the resolved AppConfig, reported by `SetupWizard` both on
  // initial load and whenever it changes `mode` — this is how App learns `engine_port`/
  // `ingest_token` without a second fetch. `useCallback` keeps this identity stable across
  // renders, which matters because `SetupWizard`'s own effects depend on it.
  const [tauriConfig, setTauriConfig] = useState<AppConfig | null>(null)
  const handleTauriConfigResolved = useCallback((cfg: AppConfig) => setTauriConfig(cfg), [])

  // Persist the token so it doesn't have to be re-entered on every page refresh.
  useEffect(() => {
    localStorage.setItem('bearerToken', token)
  }, [token])

  useEffect(() => {
    localStorage.setItem('libraryOpen', String(libraryOpen))
  }, [libraryOpen])

  // Local-mode auto-wiring (D60/T2): once the desktop shell reports mode 'local' and the engine
  // is actually up, point the SAME `apiBase`/`token` state the browser client edits by hand at
  // the local backend instead — the user never types either. Reacts to both an already-running
  // backend (checked once) and a later start (via `backend-state` events), so this works whether
  // the wizard just finished provisioning or a returning session's supervisor started it first.
  useEffect(() => {
    if (!isTauri || tauriConfig?.mode !== 'local') return
    const cfg = tauriConfig
    let disposed = false
    const disposers: (() => void)[] = []
    function wireUp() {
      setApiBase(`http://127.0.0.1:${cfg.engine_port}`)
      setToken(cfg.ingest_token)
    }
    async function watch() {
      try {
        const status = await backendStatus()
        if (!disposed && backendStateKind(status.engine.state) === 'running') wireUp()
      } catch {
        // best-effort — the event subscription below still catches a later transition
      }
      const unlisten = await listenEvent<BackendStateEvent>('backend-state', (e) => {
        if (e.component === 'engine' && backendStateKind(e.state) === 'running') wireUp()
      })
      if (disposed) {
        unlisten()
        return
      }
      disposers.push(unlisten)
    }
    void watch()
    return () => {
      disposed = true
      disposers.forEach((fn) => fn())
    }
  }, [tauriConfig])

  // Opens the System drawer already scrolled to its "Folder agent" section (D57/Task U6) — the
  // empty-corpus nudge's "Get the agent" button drives this; the drawer is always mounted (just
  // translated off-screen when closed), so the ref's `scrollIntoView` works whether or not it was
  // already open. `requestAnimationFrame` gives the `open` class one paint to apply first, so the
  // scroll lands inside a drawer that's actually laid out at its final size.
  function openAgentSection() {
    setSystemOpen(true)
    requestAnimationFrame(() => systemMenuRef.current?.scrollToAgent())
  }

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
          onOpenAgent={openAgentSection}
        />
      </div>

      <SystemMenu
        ref={systemMenuRef}
        token={token}
        setToken={setToken}
        open={systemOpen}
        onOpenChange={setSystemOpen}
      />
      <Library token={token} open={libraryOpen} onOpenChange={setLibraryOpen} />

      {/* Tauri desktop shell only (D60/T2) — a full-screen first-run overlay; renders nothing at
          all once `mode` is already set (browser bundle stays byte-identical, see `isTauri`). */}
      {isTauri && <SetupWizard onConfigResolved={handleTauriConfigResolved} onTokenChange={setToken} />}
    </>
  )
}
